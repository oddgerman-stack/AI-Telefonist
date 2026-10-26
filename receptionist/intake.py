import re
import json
import uuid
from typing import Dict, Any, Optional
from receptionist.date_parser import NaturalDateParser

class IntakeSession:
    """
    Manages structured caller intake data during a telephone session.
    Extracts caller identity, company, contact details, reason, and requested appointment time.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.caller_name: Optional[str] = None
        self.company: Optional[str] = None
        self.phone: Optional[str] = None
        self.email: Optional[str] = None
        self.reason: Optional[str] = None
        self.appointment_time_raw: Optional[str] = None
        self.appointment_time_iso: Optional[str] = None
        self.language: str = "nl"
        self.status: str = "in_progress" # in_progress, booking_confirmed, callback_requested

    def update_from_text(self, text: str, role: str = "user") -> None:
        """Inspects transcript turns and updates intake slot values using regex and heuristic extraction."""
        if not text:
            return

        # 1. Check for LLM structured JSON completion block
        if "```json" in text or '{"action":' in text:
            try:
                json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', text)
                if json_match:
                    payload = json.loads(json_match.group(0))
                    if payload.get("caller_name"):
                        self.caller_name = payload["caller_name"]
                    if payload.get("company"):
                        self.company = payload["company"]
                    if payload.get("phone"):
                        self.phone = payload["phone"]
                    if payload.get("email"):
                        self.email = payload["email"]
                    if payload.get("reason"):
                        self.reason = payload["reason"]
                    if payload.get("date_time_text"):
                        self.appointment_time_raw = payload["date_time_text"]
                        parsed_dt = NaturalDateParser.parse(payload["date_time_text"])
                        if parsed_dt:
                            self.appointment_time_iso = NaturalDateParser.format_iso(parsed_dt)

                    action = payload.get("action", "")
                    if "booking" in action:
                        self.status = "booking_confirmed"
                    elif "callback" in action:
                        self.status = "callback_requested"
                    return
            except Exception:
                pass

        if role == "user":
            # 2. Extract Email
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
            if email_match and not self.email:
                self.email = email_match.group(0)

            # 3. Extract Phone Number (Dutch / International)
            phone_match = re.search(r'(?:\+31|0031|0)[1-9][0-9\s-]{7,11}', text)
            if phone_match and not self.phone:
                self.phone = re.sub(r'[\s-]', '', phone_match.group(0))

            # 4. Extract Company Name (e.g. "namens TechCorp", "van TechCorp", "van bedrijf TechCorp")
            company_match = re.search(
                r'\b(?:namens|van het bedrijf|van bedrijf|van|from company|from)\s+([A-Z0-9][A-Za-z0-9&-]+(?:\s+[A-Z0-9][A-Za-z0-9&-]+)*)',
                text
            )
            if company_match and not self.company:
                comp_candidate = company_match.group(1).strip()
                # Exclude if it looks like a person name or stop word
                if comp_candidate.lower() not in ["mij", "mijzelf", "ons", "me", "us", "today", "tomorrow"]:
                    self.company = comp_candidate

            # 5. Extract Caller Name (stop before prepositions like 'van', 'namens', 'bij', 'from')
            name_match = re.search(
                r'\b(?:ik ben|mijn naam is|u spreekt met|met|my name is|this is|i am)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?=\s+(?:van|namens|bij|from|\.|\,)|$)',
                text,
                re.IGNORECASE
            )
            if name_match and not self.caller_name:
                cand = name_match.group(1).strip()
                if cand.lower() not in ["hallo", "goedendag", "hoi", "yes", "no"]:
                    self.caller_name = cand.title()

            # 6. Extract Date & Appointment Time cues
            time_cues = ["morgen", "overmorgen", "volgende week", "tomorrow", "next week", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "monday", "tuesday", "wednesday", "thursday", "friday"]
            if any(cue in text.lower() for cue in time_cues) and not self.appointment_time_raw:
                parsed_dt = NaturalDateParser.parse(text)
                if parsed_dt:
                    self.appointment_time_raw = text
                    self.appointment_time_iso = NaturalDateParser.format_iso(parsed_dt)
                    if not self.reason:
                        self.reason = "Afspraak inplannen"

    def is_complete_for_booking(self) -> bool:
        """Returns True if sufficient info exists to persist an appointment booking."""
        return bool(self.caller_name and (self.phone or self.email) and self.appointment_time_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Convert intake session to dictionary."""
        return {
            "session_id": self.session_id,
            "caller_name": self.caller_name or "Onbekend",
            "company": self.company or "",
            "phone": self.phone or "",
            "email": self.email or "",
            "reason": self.reason or "Algemeen contact",
            "appointment_time_raw": self.appointment_time_raw or "",
            "appointment_time_iso": self.appointment_time_iso or "",
            "language": self.language,
            "status": self.status
        }
