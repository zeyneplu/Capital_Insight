"""Create a private backend .env from its template without overwriting secrets."""

import base64
import os
from pathlib import Path
import secrets


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    destination = backend_dir / ".env"
    if destination.exists():
        print("backend/.env already exists; left unchanged.")
        return

    template = (backend_dir / ".env.example").read_text(encoding="utf-8")
    placeholder = "ENCRYPTION_KEY=\n"
    if template.count(placeholder) != 1:
        raise SystemExit("Expected exactly one empty ENCRYPTION_KEY in .env.example.")
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    content = template.replace(placeholder, f"ENCRYPTION_KEY={key}\n", 1)
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("backend/.env already exists; left unchanged.")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        output.write(content)
    print("Created backend/.env with a private encryption key. Add optional Plaid keys there.")


if __name__ == "__main__":
    main()
