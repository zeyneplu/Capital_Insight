"""Start the whole Capital Insight stack with one command.

    python scripts/dev.py            # services + core API + frontend (live mode)
    python scripts/dev.py --no-web   # services + core API only

Starts the six mock services (DEMO_MODE=true), the core API on :8000 and,
if frontend/node_modules exists, `npm run dev` with DATA_SOURCE=http.
Service logs go to logs/<name>.log. Consent codes are printed here, in a
highlighted line, so you never have to dig through logs. Ctrl+C stops all.

Development only: the printed codes are DEVELOPMENT ONLY mock codes.
"""
import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
CODE = re.compile(r"DEVELOPMENT ONLY (?:mock consent|Capital Insight sign-in) code for (\S+): (\d{6})")

BANKS = [  # id, display name, port, seed (matches services/mock_bank/compose.yaml)
    ("chase", "Chase Mock Bank", 8001, 101),
    ("amex", "American Express Mock Bank", 8002, 202),
    ("pnc", "PNC Mock Bank", 8003, 303),
    ("discover", "Discover Mock Bank", 8004, 404),
]


def services() -> list[dict]:
    uvicorn = [sys.executable, "-m", "uvicorn", "app.main:app", "--port"]
    stack = [
        {
            "name": bank_id,
            "cwd": ROOT / "services" / "mock_bank",
            "cmd": [*uvicorn, str(port)],
            "env": {"BANK_ID": bank_id, "BANK_NAME": name, "DATA_SEED": str(seed),
                    "DATABASE_URL": f"sqlite:///./data/{bank_id}.db", "DEMO_MODE": "true"},
            "health": f"http://localhost:{port}/health",
        }
        for bank_id, name, port, seed in BANKS
    ]
    stack += [
        {"name": "loans", "cwd": ROOT / "services" / "mock_loan", "cmd": [*uvicorn, "8005"],
         "env": {"DEMO_MODE": "true"}, "health": "http://localhost:8005/health"},
        {"name": "mortgages", "cwd": ROOT / "services" / "mock_mortgage", "cmd": [*uvicorn, "8006"],
         "env": {"DEMO_MODE": "true"}, "health": "http://localhost:8006/health"},
        {"name": "core-api", "cwd": ROOT / "backend", "cmd": [*uvicorn, "8000"],
         "env": {}, "health": "http://localhost:8000/health"},
    ]
    return stack


def watch(name: str, stream, log_path: Path) -> None:
    """Copies output to a log file and surfaces consent codes on the console."""
    with log_path.open("w", encoding="utf-8") as log:
        for line in iter(stream.readline, ""):
            log.write(line)
            log.flush()
            match = CODE.search(line)
            if match:
                print(f"\n  >>> {name}: code for {match.group(1)} is  {match.group(2)}\n", flush=True)
            elif "Traceback" in line or "Error" in line:
                print(f"  [{name}] {line.rstrip()}", flush=True)


def healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-web", action="store_true", help="do not start the Next.js frontend")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=3000)
    args = parser.parse_args()
    if not all(1 <= port <= 65535 for port in (args.api_port, args.web_port)):
        parser.error("Ports must be between 1 and 65535")

    if sys.version_info < (3, 10):
        print("Python 3.10+ is required (the services use modern type hints). Install it from python.org.")
        return 1
    try:
        import fastapi, httpx, faker, sqlalchemy, pydantic_settings  # noqa: F401,E401
    except ImportError as error:
        print(f"Missing Python package ({error.name}). Run:\n"
              "  pip install -r services/mock_bank/requirements.txt -r backend/requirements.txt")
        return 1

    LOGS.mkdir(exist_ok=True)
    processes: list[tuple[str, subprocess.Popen]] = []
    stack = services()
    for spec in stack:
        if spec["name"] == "core-api":
            spec["cmd"][-1] = str(args.api_port)
            spec["health"] = f"http://localhost:{args.api_port}/health"

    npm = shutil.which("npm")
    if not args.no_web:
        if npm and (ROOT / "frontend" / "node_modules").exists():
            stack.append({"name": "frontend", "cwd": ROOT / "frontend", "cmd": [shutil.which("node"), str(ROOT / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"), "dev", "--port", str(args.web_port)],
                          "env": {"DATA_SOURCE": "http", "BACKEND_API_URL": f"http://localhost:{args.api_port}"},
                          "health": f"http://localhost:{args.web_port}"})
        else:
            print("Frontend skipped: run `npm ci` in frontend/ first (and make sure Node.js is installed).")

    for spec in stack:
        process = subprocess.Popen(
            spec["cmd"], cwd=spec["cwd"], env={**os.environ, **spec["env"]},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            # Own process group, so stopping also stops grandchildren (npm -> next-server).
            **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}),
        )
        processes.append((spec["name"], process))
        threading.Thread(target=watch, args=(spec["name"], process.stdout, LOGS / f"{spec['name']}.log"), daemon=True).start()

    def kill_tree(process: subprocess.Popen, force: bool) -> None:
        if process.poll() is not None and not force:
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass

    def stop(*_):
        for _, process in processes:
            kill_tree(process, force=False)
        for _, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            kill_tree(process, force=True)  # sweep any grandchildren left in the group
        print("\nStopped everything.")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print("Starting… (logs in logs/)")
    deadline = time.time() + 90
    pending = {spec["name"]: spec["health"] for spec in stack}
    while pending and time.time() < deadline:
        for name, url in list(pending.items()):
            process = dict(processes)[name]
            if process.poll() is not None:
                print(f"  ✗ {name} exited (code {process.returncode}). See logs/{name}.log")
                pending.pop(name)
            elif healthy(url):
                print(f"  ✓ {name:<10} {url.removesuffix('/health')}")
                pending.pop(name)
        time.sleep(0.5)
    for name in pending:
        print(f"  ? {name} not ready yet; see logs/{name}.log")

    print(f"\nOpen http://localhost:{args.web_port} → Connections. Consent codes will appear here.\n"
          f"API docs: http://localhost:{args.api_port}/docs   Stop everything: Ctrl+C\n")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
