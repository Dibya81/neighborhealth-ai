import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import get_settings
from utils.logger import get_logger

logger = get_logger("NOTIFY")


def send_gmail_alert(to_email: str, ward_name: str, disease: str, score: float) -> bool:
    settings = get_settings()

    if not settings.gmail_user or not settings.gmail_app_password:
        logger.warning(
            "GMAIL_USER or GMAIL_APP_PASSWORD not configured in .env — email skipped for %s",
            to_email,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"NeighborHealth Alert: {disease} risk in {ward_name}"
    msg["From"]    = settings.gmail_user
    msg["To"]      = to_email

    text_body = (
        f"NeighborHealth Alert\n\n"
        f"Ward: {ward_name}\n"
        f"Disease: {disease}\n"
        f"Risk Score: {int(score)}/100\n\n"
        f"Take precautions today.\n"
        f"View the live map: http://localhost:3000"
    )

    html_body = f"""
    <html><body style="font-family:sans-serif;background:#f4f4f4;padding:20px;">
      <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:8px;padding:24px;">
        <h2 style="color:#c94b2c;margin:0 0 16px;">⚠️ Health Alert</h2>
        <p><strong>Ward:</strong> {ward_name}</p>
        <p><strong>Disease:</strong> {disease}</p>
        <p><strong>Risk Score:</strong>
          <span style="font-size:24px;font-weight:700;color:#c94b2c;">{int(score)}</span>/100
        </p>
        <p style="color:#666;margin-top:16px;">Take precautions today and remove any stagnant water near your home.</p>
        <a href="http://localhost:3000"
           style="display:inline-block;margin-top:16px;padding:10px 20px;background:#1db97a;color:#fff;border-radius:6px;text-decoration:none;">
          View Live Map
        </a>
      </div>
    </body></html>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.gmail_user, settings.gmail_app_password)
            server.send_message(msg)
        logger.info("Email sent successfully to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False
