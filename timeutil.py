"""Utilidades de tiempo deterministas (UTC, ISO-8601) y zona horaria local."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ISO = "%Y-%m-%dT%H:%M:%SZ"


def now_utc_iso() -> str:
    """Ahora en UTC con formato ISO-8601 (segundos, sin microsegundos)."""
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(ISO)


def parse_utc(s: str) -> datetime:
    """Convierte un ISO-8601 UTC (con o sin 'Z') a datetime aware en UTC."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_zone(name: str) -> ZoneInfo:
    """Resuelve una zona IANA. Lanza ZoneInfoNotFoundError si no existe."""
    return ZoneInfo(name)


def local_to_utc(naive: datetime, tz: str) -> datetime:
    """Convierte un datetime local *naive* a datetime UTC aware."""
    z = resolve_zone(tz)
    return naive.replace(tzinfo=z).astimezone(timezone.utc)


def utc_to_local(dt_utc: datetime, tz: str) -> datetime:
    """Convierte un datetime UTC aware a datetime local *naive*."""
    z = resolve_zone(tz)
    return dt_utc.astimezone(z).replace(tzinfo=None)


def parse_hhmm(hhmm: str):
    """'08:00' -> datetime.time. Lanza ValueError si el formato es inválido."""
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def next_occurrence_utc(t: time, tz: str, after: datetime) -> datetime:
    """Siguiente ocurrencia de la hora local 't' estrictamente después de 'after' (UTC).

    Si 'after' es anterior a la hora de hoy en la zona, devuelve la de hoy; si no, la de mañana.
    """
    z = resolve_zone(tz)
    local_now = after.astimezone(z).replace(tzinfo=None)
    candidate = datetime.combine(local_now.date(), t)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.replace(tzinfo=z).astimezone(timezone.utc)
