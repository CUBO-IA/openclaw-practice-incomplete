"""Agente de registro/historial: consulta de eventos recientes."""
from .response import ok, need


def history(con, payload):
    pid = payload.get("patient_id")
    if pid is None:
        return need(["patient_id"])
    limit = min(int(payload.get("limit", 20)), 100)
    rows = con.execute(
        "SELECT id, ts, actor, action, entity, entity_id FROM audit_event "
        "WHERE entity_id IN (SELECT id FROM patient WHERE id=?) OR entity IN ('medication_event','exercise_event','appointment','reminder') "
        "ORDER BY id DESC LIMIT ?", (pid, limit),
    ).fetchall()
    return ok(f"{len(rows)} eventos", data_refs=[r["id"] for r in rows])
