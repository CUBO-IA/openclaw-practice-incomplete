"""Agente de control: verificaciones básicas de consistencia."""
from .response import ok


def check(con, payload=None):
    payload = payload or {}
    alerts = []
    failed_reminders = con.execute(
        "SELECT COUNT(*) FROM reminder WHERE status='failed'").fetchone()[0]
    failed_notifs = con.execute(
        "SELECT COUNT(*) FROM notification_event WHERE status='failed'").fetchone()[0]
    if failed_reminders:
        alerts.append({"type": "reminder_failed", "count": failed_reminders})
    if failed_notifs:
        alerts.append({"type": "notification_failed", "count": failed_notifs})
    return ok("control ejecutado", alerts=alerts, data_refs=[])
