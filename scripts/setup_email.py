"""Prepare private mail configuration and its internal forwarding key."""
from pathlib import Path
import os
import secrets


def main():
    root=Path(__file__).resolve().parents[1]
    path=root/".env.mail"
    content=path.read_text(encoding="utf-8") if path.exists() else (root/".env.mail.example").read_text(encoding="utf-8")
    lines=content.splitlines()
    changed=not path.exists()
    found=False
    for index,line in enumerate(lines):
        if line.startswith("MOCK_SERVICE_API_KEY="):
            found=True
            if not line.split("=",1)[1].strip():
                lines[index]="MOCK_SERVICE_API_KEY="+secrets.token_urlsafe(48)
                changed=True
    if not found:
        lines.append("MOCK_SERVICE_API_KEY="+secrets.token_urlsafe(48))
        changed=True
    if changed:
        path.write_text("\n".join(lines)+"\n",encoding="utf-8")
        os.chmod(path,0o600)
    print("Private .env.mail is ready. Add SMTP credentials locally; no secrets were printed.")


if __name__ == "__main__":
    main()
