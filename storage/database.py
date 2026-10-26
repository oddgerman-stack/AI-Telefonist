import os
import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from core.config import config

class AppointmentDatabase:
    """
    Thread-safe JSON appointments database (`appointments.json`).
    Provides CRUD operations, conflict checking, and persistence.
    """

    def __init__(self, filename: Optional[str] = None):
        configured_file = filename or config.get("storage.appointments_file", "appointments.json")
        self.db_path = config.resolve_path(configured_file)
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create appointments.json with empty list if it does not exist."""
        if not self.db_path.exists():
            with self._lock:
                try:
                    with open(self.db_path, "w", encoding="utf-8") as f:
                        json.dump([], f, indent=2)
                except Exception as e:
                    print(f"[DB] Error creating database file {self.db_path}: {e}")

    def list_all(self, status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all appointments with optional status filtering and search query."""
        with self._lock:
            try:
                if not self.db_path.exists():
                    return []
                with open(self.db_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception as e:
                print(f"[DB] Error reading appointments: {e}")
                records = []

        if status and status != "all":
            records = [r for r in records if r.get("status") == status]

        if search:
            q = search.lower()
            records = [
                r for r in records
                if q in r.get("caller_name", "").lower()
                or q in r.get("company", "").lower()
                or q in r.get("phone", "").lower()
                or q in r.get("email", "").lower()
                or q in r.get("reason", "").lower()
            ]

        # Sort descending by creation date
        records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return records

    def get_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an appointment by its unique identifier."""
        records = self.list_all()
        for r in records:
            if r.get("id") == appointment_id:
                return r
        return None

    def check_conflict(self, start_iso: str, duration_minutes: int = 30) -> Optional[Dict[str, Any]]:
        """
        Check if a given start time conflicts with an existing confirmed appointment.
        Returns the conflicting appointment if any, otherwise None.
        """
        try:
            target_start = datetime.fromisoformat(start_iso)
            target_end = target_start + timedelta(minutes=duration_minutes)
        except Exception:
            return None

        records = self.list_all(status="confirmed")
        for r in records:
            r_start_str = r.get("start_time")
            if not r_start_str:
                continue
            try:
                r_start = datetime.fromisoformat(r_start_str)
                r_duration = r.get("duration_minutes", 30)
                r_end = r_start + timedelta(minutes=r_duration)

                # Overlap test: (target_start < r_end) and (target_end > r_start)
                if target_start < r_end and target_end > r_start:
                    return r
            except Exception:
                continue

        return None

    def add(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new appointment record."""
        appointment_id = data.get("id") or str(uuid.uuid4())
        created_at = data.get("created_at") or datetime.now().isoformat()
        
        record = {
            "id": appointment_id,
            "caller_name": data.get("caller_name", "Onbekend"),
            "company": data.get("company", ""),
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "reason": data.get("reason", "Afspraak"),
            "start_time": data.get("start_time") or data.get("appointment_time_iso") or datetime.now().isoformat(),
            "duration_minutes": data.get("duration_minutes", 30),
            "status": data.get("status", "confirmed"), # confirmed, pending, cancelled
            "language": data.get("language", "nl"),
            "created_at": created_at,
            "dispatched": data.get("dispatched", False),
            "notes": data.get("notes", "")
        }

        with self._lock:
            all_records = []
            try:
                if self.db_path.exists():
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        all_records = json.load(f)
            except Exception:
                all_records = []

            all_records.append(record)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(all_records, f, indent=2, ensure_ascii=False)

        print(f"[DB] Saved new appointment ID: {appointment_id} for {record['caller_name']}")
        return record

    def update_status(self, appointment_id: str, new_status: str) -> bool:
        """Updates the status of an appointment."""
        with self._lock:
            all_records = []
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    all_records = json.load(f)
            except Exception:
                return False

            updated = False
            for r in all_records:
                if r.get("id") == appointment_id:
                    r["status"] = new_status
                    updated = True
                    break

            if updated:
                with open(self.db_path, "w", encoding="utf-8") as f:
                    json.dump(all_records, f, indent=2, ensure_ascii=False)

            return updated

    def mark_dispatched(self, appointment_id: str) -> bool:
        """Mark notification dispatch as completed."""
        with self._lock:
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    all_records = json.load(f)
            except Exception:
                return False

            for r in all_records:
                if r.get("id") == appointment_id:
                    r["dispatched"] = True
                    break

            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(all_records, f, indent=2, ensure_ascii=False)
            return True

    def delete(self, appointment_id: str) -> bool:
        """Remove an appointment by ID."""
        with self._lock:
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    all_records = json.load(f)
            except Exception:
                return False

            orig_len = len(all_records)
            all_records = [r for r in all_records if r.get("id") != appointment_id]
            if len(all_records) != orig_len:
                with open(self.db_path, "w", encoding="utf-8") as f:
                    json.dump(all_records, f, indent=2, ensure_ascii=False)
                return True
            return False

# Global instance
db = AppointmentDatabase()
