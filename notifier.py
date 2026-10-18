"""Notifier: interfaz de envío con adaptadores intercambiables.

Regla: nunca afirmar entrega sin confirmación técnica.
Fase 2 solo tiene el adaptador 'local'; los externos son stubs que
responden blocked: no_configurado (se completan en Fase 3).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SendResult:
    status: str            # sent | delivered | failed | blocked
    provider_message_id: str = None
    error: str = None


class LocalAdapter:
    """Aviso local (pantalla/Windows). Registra los envíos para pruebas."""

    name = "local"

    def __init__(self):
        self.sent = []

    def send(self, target, message):
        entry = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
            "target": target,
            "message": message,
        }
        self.sent.append(entry)
        # Local: entrega confirmada al mostrarse en el equipo (sin red externa).
        return SendResult(status="delivered", provider_message_id=f"local:{len(self.sent)}")


class _BlockedAdapter:
    """Stub para canales no configurados todavía."""

    def __init__(self, name):
        self.name = name

    def send(self, target, message):
        return SendResult(status="blocked", error="no_configurado")


class Notifier:
    def __init__(self):
        self.adapters = {
            "local": LocalAdapter(),
            "telegram": _BlockedAdapter("telegram"),
            "whatsapp": _BlockedAdapter("whatsapp"),
            "discord": _BlockedAdapter("discord"),
            "sms": _BlockedAdapter("sms"),
        }

    def send(self, channel, target, message):
        adapter = self.adapters.get(channel)
        if adapter is None:
            return SendResult(status="blocked", error=f"canal_desconocido:{channel}")
        return adapter.send(target, message)
