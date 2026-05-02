import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config


def _send_via_smtp(to_addr: str, body: str, subject: str = "") -> bool:
    """Send an email via SMTP."""
    if not all([config.SMTP_EMAIL, config.SMTP_PASSWORD]):
        print("[SMTP] Missing SMTP_EMAIL or SMTP_PASSWORD. Cannot send.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = config.SMTP_EMAIL
        msg["To"] = to_addr
        if subject:
            msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        if subject:
            html_body = "<pre style='font-family: Arial, sans-serif; font-size: 14px;'>"
            html_body += body.replace("\n", "<br>")
            html_body += "</pre>"
            msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_EMAIL, to_addr, msg.as_string())

        return True
    except Exception as e:
        print(f"[SMTP] Failed to send to {to_addr}: {e}")
        return False


def send_email(body: str, subject: str = "Your Daily News Briefing") -> bool:
    """Send the briefing via email using SMTP. Returns True on success."""
    if not config.USER_EMAIL:
        print("[Email] No USER_EMAIL configured. Skipping email.")
        return False

    print(f"[Email] Sending to {config.USER_EMAIL}...")
    if _send_via_smtp(config.USER_EMAIL, body, subject=subject):
        print(f"[Email] Sent successfully to {config.USER_EMAIL}")
        return True
    return False


def deliver(body: str) -> bool:
    """Deliver the briefing via email."""
    print("[Delivery] Attempting to deliver briefing...")
    if send_email(body):
        return True

    print("[Delivery] Email failed. Printing to console as last resort.")
    print("=" * 60)
    print(body)
    print("=" * 60)
    return False
