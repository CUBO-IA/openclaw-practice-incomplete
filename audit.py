"""Auditoría append-only.

Toda mutación relevante pasa por aquí. La tabla audit_event tiene triggers en el
schema que impiden UPDATE/DELETE, así que el registro es de solo agregar.
"""
import json

from .timeutil import now_utc_iso

VALID_ORIGINS = ("user", "agent", "import", "system")


def _dump(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def record(con, *, actor, actor_role=None, action, entity, entity_id=None,
           old_value=None, new_value=None, reason=None, origin="agent"):
    """Inserta un evento de auditoría. Lanza ValueError si el origen no es válido."""
    if origin not in VALID_ORIGINS:
        raise ValueError(f"origin inválido: {origin}")
    con.execute(
        "INSERT INTO audit_event (ts, actor, actor_role, action, entity, entity_id,\n"
        "                          old_value, new_value, reason, origin)\n"
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now_utc_iso(), actor, actor_role, action, entity, entity_id,
         _dump(old_value), _dump(new_value), reason, origin),
    )
    return con.execute("SELECT last_insert_rowid()").fetchone()[0]
