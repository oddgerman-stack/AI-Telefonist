import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from core.config import config

class ICalGenerator:
    """
    RFC 5545 Compliant iCalendar (.ics) Generator.
    Produces valid calendar invitations compatible with Outlook, Google Calendar, Apple Calendar.
    """

    @classmethod
    def generate(cls, appointment: Dict[str, Any]) -> str:
        """
        Generates RFC 5545 compliant VCALENDAR text for an appointment.
        """
        biz_name = config.get("business.name", "Acme Bedrijf B.V.")
        biz_email = config.get("business.email", "info@example.com")
        biz_phone = config.get("business.phone", "+31 20 123 4567")

        uid = appointment.get("id") or str(uuid.uuid4())
        caller_name = appointment.get("caller_name", "Klant")
        caller_email = appointment.get("email", "")
        caller_phone = appointment.get("phone", "")
        company = appointment.get("company", "")
        reason = appointment.get("reason", "Afspraak")
        
        # Parse start and end time
        start_iso = appointment.get("start_time") or datetime.now().isoformat()
        try:
            start_dt = datetime.fromisoformat(start_iso)
        except Exception:
            start_dt = datetime.now() + timedelta(days=1, hours=10)

        duration_mins = appointment.get("duration_minutes", 30)
        end_dt = start_dt + timedelta(minutes=duration_mins)

        # RFC 5545 UTC date formatting
        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dtstart_str = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend_str = end_dt.strftime("%Y%m%dT%H%M%S")

        summary = f"Afspraak: {caller_name}" + (f" ({company})" if company else "") + f" - {biz_name}"
        
        description_lines = [
            f"Afspraak met: {caller_name}",
            f"Bedrijf: {company or 'Particulier'}",
            f"Telefoon: {caller_phone or 'Niet opgegeven'}",
            f"E-mail: {caller_email or 'Niet opgegeven'}",
            f"Onderwerp / Reden: {reason}",
            f"Organisatie: {biz_name} ({biz_phone})"
        ]
        description = "\\n".join(description_lines)

        attendee_line = ""
        if caller_email:
            attendee_line = f"ATTENDEE;CN={caller_name};ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{caller_email}\r\n"

        # Standard RFC 5545 format with CRLF line endings
        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//AI-Telefonist//Virtual Receptionist//NL\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:REQUEST\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}@ai-telefonist.local\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART:{dtstart_str}\r\n"
            f"DTEND:{dtend_str}\r\n"
            f"SUMMARY:{summary}\r\n"
            f"DESCRIPTION:{description}\r\n"
            f"ORGANIZER;CN=\"{biz_name}\":mailto:{biz_email}\r\n"
            f"{attendee_line}"
            "STATUS:CONFIRMED\r\n"
            "SEQUENCE:0\r\n"
            "BEGIN:VALARM\r\n"
            "TRIGGER:-PT15M\r\n"
            "ACTION:DISPLAY\r\n"
            "DESCRIPTION:Herinnering: Afspraak begint over 15 minuten\r\n"
            "END:VALARM\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )

        return ics_content

    @classmethod
    def generate_bytes(cls, appointment: Dict[str, Any]) -> bytes:
        """Returns the .ics invite as UTF-8 bytes."""
        return cls.generate(appointment).encode("utf-8")
