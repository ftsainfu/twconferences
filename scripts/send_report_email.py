#!/usr/bin/env python3
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


def main() -> int:
    recipient = os.environ.get("REPORT_EMAIL", "ftsainfu@gmail.com")
    username = os.environ.get("SMTP_USERNAME") or recipient
    password = os.environ.get("SMTP_APP_PASSWORD", "")
    summary_path = Path(os.environ["REPORT_SUMMARY"])
    if not password:
        print("SMTP secrets are not configured; skipping email notification.", file=sys.stderr)
        return 0
    message = EmailMessage()
    message["Subject"] = os.environ.get("REPORT_SUBJECT", "twconferences 使用者資料回報")
    message["From"] = username
    message["To"] = recipient
    message.set_content(summary_path.read_text(encoding="utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
