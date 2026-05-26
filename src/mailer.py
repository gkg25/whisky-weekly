from __future__ import annotations
import argparse
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def parse_recipients(value) -> list[str]:
    """list / カンマ区切り文字列 / 単一文字列のどれでも受け入れて list[str] に正規化。"""
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = value.split(",")
    else:
        raise TypeError("recipients must be a list or a comma-separated string")
    return [r.strip() for r in items if r.strip()]


def send_email(
    *,
    sender: str,
    password: str,
    recipients,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    attachments: Optional[list[Path]] = None,
    sender_name: str = "Whisky Weekly",
) -> list[str]:
    """recipients は list か カンマ区切り文字列。BCC で一括送信し、解決済み受信者リストを返す。"""
    recipient_list = parse_recipients(recipients)
    if not recipient_list:
        raise ValueError("at least one recipient is required")

    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((str(sender_name), sender))
    msg["To"] = sender
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        alt.attach(MIMEText(body_html, "html", "utf-8"))
    msg.attach(alt)

    for path in attachments or []:
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), Name=path.name)
        part["Content-Disposition"] = f'attachment; filename="{path.name}"'
        msg.attach(part)

    all_envelope_recipients = list({sender, *recipient_list})

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.send_message(msg, from_addr=sender, to_addrs=all_envelope_recipients)

    return recipient_list


def main():
    parser = argparse.ArgumentParser(description="Gmail SMTP 経由でメール送信")
    parser.add_argument("--subject", default="[Whisky Weekly] テスト送信")
    parser.add_argument("--body", default="Whisky Weekly システムからのテストメールです。\nこのメールが届いていれば Gmail アプリパスワード設定は正常です。")
    parser.add_argument("--html", default=None, help="HTML本文（任意）")
    parser.add_argument("--attach", action="append", default=[], help="添付ファイル（複数指定可）")
    parser.add_argument("--to", default=None, help="受信先（カンマ区切りで複数可。未指定なら RECIPIENT_EMAIL）")
    args = parser.parse_args()

    load_dotenv()
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient_value = args.to or os.environ.get("RECIPIENT_EMAIL")

    if not sender or not password or not recipient_value:
        raise SystemExit("GMAIL_ADDRESS / GMAIL_APP_PASSWORD / RECIPIENT_EMAIL を .env に設定してください")

    attachments = [Path(p) for p in args.attach]
    for a in attachments:
        if not a.exists():
            raise SystemExit(f"添付ファイルが見つかりません: {a}")

    recipient_list = send_email(
        sender=sender,
        password=password,
        recipients=recipient_value,
        subject=args.subject,
        body_text=args.body,
        body_html=args.html,
        attachments=attachments,
    )
    print(f"Sent: subject={args.subject!r}")
    print(f"Recipients ({len(recipient_list)}): {recipient_list}")
    if attachments:
        print(f"Attachments: {[a.name for a in attachments]}")


if __name__ == "__main__":
    main()
