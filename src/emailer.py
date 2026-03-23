"""
Send digest via email using Gmail SMTP.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import markdown


def send_digest(digest_md: str, date_str: str):
    """Send the digest as an HTML email via Gmail SMTP."""

    sender = os.environ.get("GMAIL_ADDRESS", "zytzrh@gmail.com")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = sender  # Send to self

    if not password:
        raise ValueError("GMAIL_APP_PASSWORD not set")

    # Convert markdown to HTML
    html_content = markdown.markdown(digest_md, extensions=["tables", "fenced_code"])

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Paper Digest - {date_str}"
    msg["From"] = f"Paper Digest <{sender}>"
    msg["To"] = recipient

    # Attach both plain text and HTML
    msg.attach(MIMEText(digest_md, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    # Send via Gmail SMTP
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
