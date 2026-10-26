import threading
from typing import Dict, Any
from notifications.email_service import EmailService
from notifications.webhook_service import WebhookService
from notifications.calendar_sync import CalendarSyncService
from storage.database import db

class NotificationDispatcher:
    """
    Central Asynchronous Multi-Channel Dispatcher.
    Triggers SMTP Email, Webhooks, and Calendar Sync upon new appointment creation.
    """

    @classmethod
    def dispatch_appointment(cls, appointment: Dict[str, Any]) -> None:
        """Dispatches notifications concurrently in a background thread."""
        def worker():
            app_id = appointment.get("id")
            print(f"[Dispatcher] Starting multi-channel dispatch for appointment {app_id}...")

            # 1. SMTP Email with .ics attachment
            email_ok = EmailService.send_appointment_notification(appointment)

            # 2. Webhooks (Discord, Slack, n8n/Zapier)
            webhook_results = WebhookService.dispatch_all(appointment)

            # 3. Calendar Sync stubs
            CalendarSyncService.sync_to_google_calendar(appointment)
            CalendarSyncService.sync_to_cal_com(appointment)

            # Mark dispatched in database
            if app_id:
                db.mark_dispatched(app_id)
            print(f"[Dispatcher] Dispatch complete for {app_id} (Email: {email_ok}, Webhooks: {webhook_results})")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
