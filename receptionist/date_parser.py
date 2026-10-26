import re
from datetime import datetime, timedelta, date, time
from typing import Optional, Tuple

class NaturalDateParser:
    """
    Parses natural Dutch and English date-time expressions into standard ISO-8601 datetimes.
    Examples:
    - 'morgen om 14 uur' -> Tomorrow at 14:00:00
    - 'volgende week maandag om 10:30' -> Next Monday at 10:30:00
    - 'overmorgen rond 15u' -> Day after tomorrow at 15:00:00
    - 'next Monday at 10 AM' -> Next Monday at 10:00:00
    - 'tomorrow afternoon at 2' -> Tomorrow at 14:00:00
    """

    DUTCH_WEEKDAYS = {
        "maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3,
        "vrijdag": 4, "zaterdag": 5, "zondag": 6
    }

    ENGLISH_WEEKDAYS = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }

    @classmethod
    def parse(cls, text: str, reference_datetime: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parses text and returns a timezone-naive or local datetime, or None if unrecognized.
        """
        if not text:
            return None

        now = reference_datetime or datetime.now()
        clean = text.lower().strip()

        target_date = None
        target_time = None

        # 1. Parse Day / Date
        if "overmorgen" in clean or "day after tomorrow" in clean:
            target_date = (now + timedelta(days=2)).date()
        elif "morgen" in clean or "tomorrow" in clean:
            target_date = (now + timedelta(days=1)).date()
        elif "vandaag" in clean or "today" in clean:
            target_date = now.date()

        # Check for weekdays (Dutch & English)
        if target_date is None:
            # Check for "volgende week <dag>" or "next <day>"
            is_next_week = "volgende week" in clean or "next week" in clean or "next " in clean
            
            for name, weekday_idx in {**cls.DUTCH_WEEKDAYS, **cls.ENGLISH_WEEKDAYS}.items():
                if name in clean:
                    days_ahead = weekday_idx - now.weekday()
                    if days_ahead <= 0 or is_next_week:
                        days_ahead += 7
                    target_date = (now + timedelta(days=days_ahead)).date()
                    break

        # Check for explicit date like "25 november", "12-10", "15/11"
        if target_date is None:
            explicit_date = re.search(r'\b(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{2,4}))?\b', clean)
            if explicit_date:
                day = int(explicit_date.group(1))
                month = int(explicit_date.group(2))
                year = int(explicit_date.group(3)) if explicit_date.group(3) else now.year
                if year < 100:
                    year += 2000
                try:
                    target_date = date(year, month, day)
                except ValueError:
                    pass

        # If date could not be parsed, default to tomorrow
        if target_date is None:
            target_date = (now + timedelta(days=1)).date()

        # 2. Parse Time
        # Prioritize explicit time formats: "om 14:00", "14:30", "14 uur", "at 2 PM", "10:00 am"
        time_match = re.search(r'\b(?:om|at|rond|around)\s+(\d{1,2})(?:[:.u](\d{2}))?\s*(am|pm|uur|u)?\b', clean)
        if not time_match:
            # Match formats with explicit colon or meridiem/uur (e.g. "14:00", "2 pm", "15u30")
            time_match = re.search(r'\b(\d{1,2})[:.u](\d{2})\s*(am|pm|uur|u)?\b', clean)
        if not time_match:
            time_match = re.search(r'\b(\d{1,2})\s*(am|pm|uur)\b', clean)
        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2)) if time_match.group(2) else 0
            meridiem = time_match.group(3)

            # Check for 's middags / 's avonds / 's ochtends
            is_afternoon = bool(re.search(r"('s middags|'s avonds|middag|afternoon|pm|evening)", clean))
            is_morning = bool(re.search(r"('s ochtends|ochtend|morning|am)", clean))

            if meridiem and meridiem.lower() == "pm" and hours < 12:
                hours += 12
            elif meridiem and meridiem.lower() == "am" and hours == 12:
                hours = 0
            elif is_afternoon and hours < 12:
                hours += 12
            elif is_morning and hours == 12:
                hours = 0

            # Guard against invalid times
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                target_time = time(hours, minutes)

        # Default time: 10:00 AM if no time was specified
        if target_time is None:
            target_time = time(10, 0)

        return datetime.combine(target_date, target_time)

    @classmethod
    def format_iso(cls, dt: datetime) -> str:
        """Returns ISO 8601 formatted string."""
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    @classmethod
    def format_friendly_nl(cls, dt: datetime) -> str:
        """Returns readable Dutch format: 'woensdag 28 oktober om 14:00 uur'."""
        nl_days = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
        nl_months = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
        day_str = nl_days[dt.weekday()]
        month_str = nl_months[dt.month - 1]
        return f"{day_str} {dt.day} {month_str} {dt.year} om {dt.strftime('%H:%M')} uur"
