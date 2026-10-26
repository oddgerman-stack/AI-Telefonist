import json
import requests
from typing import Dict, Any
from core.config import config

class WebhookService:
    """
    Multi-Channel Webhook Dispatcher.
    Formats and delivers instant JSON payloads to Discord, Slack, n8n, and Zapier.
    """

    @classmethod
    def dispatch_all(cls, appointment: Dict[str, Any]) -> Dict[str, bool]:
        """Dispatches notification to all enabled webhooks."""
        webhooks_cfg = config.get("notifications.webhooks", {})
        if not webhooks_cfg.get("enabled", False):
            return {}

        results = {}
        discord_url = webhooks_cfg.get("discord_url")
        slack_url = webhooks_cfg.get("slack_url")
        generic_url = webhooks_cfg.get("generic_webhook_url")

        if discord_url:
            results["discord"] = cls.send_discord(discord_url, appointment)
        if slack_url:
            results["slack"] = cls.send_slack(slack_url, appointment)
        if generic_url:
            results["generic"] = cls.send_generic(generic_url, appointment)

        return results

    @classmethod
    def send_discord(cls, webhook_url: str, appointment: Dict[str, Any]) -> bool:
        """Sends rich Discord embed."""
        caller = appointment.get("caller_name", "Onbekend")
        company = appointment.get("company", "N/A")
        phone = appointment.get("phone", "N/A")
        email = appointment.get("email", "N/A")
        time_slot = appointment.get("start_time", "N/A")
        reason = appointment.get("reason", "Afspraak")

        payload = {
            "username": "AI-Telefonist",
            "avatar_url": "https://img.icons8.com/fluency/96/phone-disconnected.png",
            "embeds": [
                {
                    "title": f"📞 Nieuwe Afspraak: {caller}",
                    "color": 3066993, # Emerald / Green
                    "fields": [
                        {"name": "Bedrijf", "value": company or "Niet opgegeven", "inline": True},
                        {"name": "Telefoon", "value": phone or "Niet opgegeven", "inline": True},
                        {"name": "E-mail", "value": email or "Niet opgegeven", "inline": True},
                        {"name": "Datum & Tijd", "value": time_slot, "inline": False},
                        {"name": "Onderwerp / Reden", "value": reason, "inline": False}
                    ],
                    "footer": {
                        "text": "AI-Telefonist • 100% Offline Front-Desk"
                    }
                }
            ]
        }

        try:
            res = requests.post(webhook_url, json=payload, timeout=5)
            success = res.status_code in [200, 204]
            if success:
                print("[Webhook] Dispatched to Discord successfully.")
            else:
                print(f"[Webhook] Discord returned status {res.status_code}: {res.text}")
            return success
        except Exception as e:
            print(f"[Webhook] Discord dispatch error: {e}")
            return False

    @classmethod
    def send_slack(cls, webhook_url: str, appointment: Dict[str, Any]) -> bool:
        """Sends Slack Block Kit message card."""
        caller = appointment.get("caller_name", "Onbekend")
        company = appointment.get("company", "N/A")
        phone = appointment.get("phone", "N/A")
        email = appointment.get("email", "N/A")
        time_slot = appointment.get("start_time", "N/A")
        reason = appointment.get("reason", "Afspraak")

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📞 Nieuwe Afspraak: {caller}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Bedrijf:*\n{company}"},
                        {"type": "mrkdwn", "text": f"*Telefoon:*\n{phone}"},
                        {"type": "mrkdwn", "text": f"*E-mail:*\n{email}"},
                        {"type": "mrkdwn", "text": f"*Datum & Tijd:*\n{time_slot}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Onderwerp / Reden:*\n{reason}"
                    }
                }
            ]
        }

        try:
            res = requests.post(webhook_url, json=payload, timeout=5)
            success = res.status_code == 200
            if success:
                print("[Webhook] Dispatched to Slack successfully.")
            else:
                print(f"[Webhook] Slack returned status {res.status_code}")
            return success
        except Exception as e:
            print(f"[Webhook] Slack dispatch error: {e}")
            return False

    @classmethod
    def send_generic(cls, webhook_url: str, appointment: Dict[str, Any]) -> bool:
        """Dispatches standard JSON webhook payload for n8n, Zapier or Make."""
        payload = {
            "event": "appointment_booked",
            "data": appointment
        }

        try:
            res = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
            success = res.status_code in [200, 201, 202, 204]
            if success:
                print("[Webhook] Dispatched to generic webhook (n8n/Zapier) successfully.")
            return success
        except Exception as e:
            print(f"[Webhook] Generic webhook dispatch error: {e}")
            return False
