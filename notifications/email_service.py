import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional
from core.config import config
from storage.ical_generator import ICalGenerator

class EmailService:
    """
    SMTP Email Notification Service.
    Dispatches formatted HTML appointment summaries with attached standard .ics calendar files.
    """

    @classmethod
    def send_appointment_notification(cls, appointment: Dict[str, Any]) -> bool:
        """Sends an HTML summary email with .ics attachment via SMTP."""
        smtp_cfg = config.get("notifications.smtp", {})
        if not smtp_cfg.get("enabled", False):
            print("[Email] SMTP dispatch is disabled in config.")
            return False

        host = smtp_cfg.get("host")
        port = smtp_cfg.get("port", 587)
        username = smtp_cfg.get("username")
        password = smtp_cfg.get("password")
        sender = smtp_cfg.get("sender_email") or username
        recipient = smtp_cfg.get("recipient_email") or sender
        use_tls = smtp_cfg.get("use_tls", True)

        if not host or not recipient:
            print("[Email] Missing SMTP host or recipient.")
            return False

        caller_name = appointment.get("caller_name", "Klant")
        company = appointment.get("company", "Niet opgegeven")
        phone = appointment.get("phone", "Niet opgegeven")
        email = appointment.get("email", "Niet opgegeven")
        reason = appointment.get("reason", "Afspraak")
        start_time = appointment.get("start_time", "Onbekend")

        subject = f"📅 Nieuwe Afspraak: {caller_name} ({company})"

        # Build clean responsive HTML body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
                .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e2e8f0; }}
                .header {{ background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #ffffff; padding: 24px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
                .content {{ padding: 28px; }}
                .badge {{ display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; background: #dbeafe; color: #1e40af; margin-bottom: 16px; }}
                .table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
                .table td {{ padding: 10px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
                .table td.label {{ color: #64748b; font-weight: 500; width: 35%; }}
                .table td.val {{ color: #0f172a; font-weight: 600; }}
                .footer {{ background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header">
                    <h1>AI-Telefonist Notificatie</h1>
                </div>
                <div class="content">
                    <span class="badge">Afspraak Bevestigd</span>
                    <p>Er is zojuist een nieuw telefoongesprek afgerond en een afspraak ingepland.</p>
                    <table class="table">
                        <tr><td class="label">Beller:</td><td class="val">{caller_name}</td></tr>
                        <tr><td class="label">Bedrijf:</td><td class="val">{company}</td></tr>
                        <tr><td class="label">Telefoon:</td><td class="val">{phone}</td></tr>
                        <tr><td class="label">E-mail:</td><td class="val">{email}</td></tr>
                        <tr><td class="label">Datum & Tijd:</td><td class="val">{start_time}</td></tr>
                        <tr><td class="label">Onderwerp / Reden:</td><td class="val">{reason}</td></tr>
                    </table>
                    <p style="margin-top: 20px; font-size: 13px; color: #64748b;">
                        <em>De bijgevoegde .ics kalenderuitnodiging kan direct worden geopend om deze afspraak toe te voegen aan Outlook of Google Agenda.</em>
                    </p>
                </div>
                <div class="footer">
                    Gegenereerd door AI-Telefonist &bull; 100% Offline Front-Desk Engine
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        # Attach HTML body
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Attach .ics calendar file
        try:
            ics_str = ICalGenerator.generate(appointment)
            attachment = MIMEBase("text", "calendar", method="REQUEST", name="afspraak.ics")
            attachment.set_payload(ics_str.encode("utf-8"))
            encoders.encode_base64(attachment)
            attachment.add_header("Content-Disposition", "attachment", filename="afspraak.ics")
            attachment.add_header("Content-Class", "urn:content-classes:calendarmessage")
            msg.attach(attachment)
        except Exception as e:
            print(f"[Email] Error generating .ics attachment: {e}")

        # Dispatch via SMTP
        try:
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                if use_tls:
                    server.starttls()

            if username and password:
                server.login(username, password)

            server.sendmail(sender, [recipient], msg.as_string())
            server.quit()
            print(f"[Email] Successfully dispatched appointment confirmation email to {recipient}")
            return True
        except Exception as e:
            print(f"[Email] SMTP dispatch failed: {e}")
            return False
