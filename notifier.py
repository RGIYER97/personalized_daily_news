import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config


# Most US carriers support Email-to-SMS gateways. Send an email to
# <10-digit-number>@<carrier-gateway> and it arrives as a text message.
CARRIER_GATEWAYS = {
    "att":      "txt.att.net",
    "tmobile":  "tmomail.net",
    "verizon":  "vtext.com",
    "sprint":   "messaging.sprintpcs.com",
    "uscellular": "email.uscc.net",
    "boost":    "sms.myboostmobile.com",
    "cricket":  "sms.cricketwireless.net",
    "metro":    "mymetropcs.com",
    "mint":     "tmomail.net",           # Mint uses T-Mobile's network
    "googlefi": "msg.fi.google.com",
    "xfinity":  "vtext.com",            # Xfinity Mobile uses Verizon
    "visible":  "vtext.com",            # Visible uses Verizon
}

SMS_CHAR_LIMIT = 1500


def _get_sms_email_address() -> str | None:
    """Build the email-to-SMS address from phone number + carrier."""
    phone = config.USER_PHONE.strip().lstrip("+1").replace("-", "").replace(" ", "")
    carrier = config.USER_CARRIER.strip().lower()

    if not phone or not carrier:
        return None

    if len(phone) != 10 or not phone.isdigit():
        print(f"[SMS] Phone number must be 10 digits (got '{phone}'). Skipping SMS.")
        return None

    gateway = CARRIER_GATEWAYS.get(carrier)
    if not gateway:
        print(f"[SMS] Unknown carrier '{carrier}'. Supported: {', '.join(sorted(CARRIER_GATEWAYS))}")
        return None

    return f"{phone}@{gateway}"


def _send_via_smtp(to_addr: str, body: str, subject: str = "") -> bool:
    """Send an email/SMS via SMTP. Used by both SMS gateway and email delivery."""
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


def send_sms(body: str) -> bool:
    """Send the briefing as an SMS via Email-to-SMS gateway. Returns True on success."""
    sms_addr = _get_sms_email_address()
    if not sms_addr:
        print("[SMS] Email-to-SMS not configured. Skipping SMS.")
        return False

    if len(body) > SMS_CHAR_LIMIT:
        print(f"[SMS] Message too long ({len(body)} chars). Falling back to email.")
        return False

    print(f"[SMS] Sending via gateway: {sms_addr}")
    if _send_via_smtp(sms_addr, body):
        print("[SMS] Sent successfully via Email-to-SMS gateway.")
        return True
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
    """Try SMS first, fall back to email if SMS fails or message is too long."""
    print("[Delivery] Attempting to deliver briefing...")
    if send_sms(body):
        return True

    print("[Delivery] SMS unavailable or too long. Trying email fallback...")
    if send_email(body):
        return True

    print("[Delivery] All delivery methods failed. Printing to console as last resort.")
    print("=" * 60)
    print(body)
    print("=" * 60)
    return False
