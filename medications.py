"""Agente de medicamentos: listar activos, stock y registro de toma."""
from ..core.audit import record
from ..core.repositories import MedicationRepository, Actor
from ..core.timeutil import now_utc_iso
from .response import ok, need, blocked
import json


def _actor(payload):
    return Actor(username=payload.get("actor", "agent"), role=payload.get("role", "clinician"),
                 patient_id=payload.get("actor_patient_id"))


def list_medications(con, payload):
    pid = payload.get("patient_id")
    if pid is None:
        return need(["patient_id"])
    rows = MedicationRepository(con).list_active(_actor(payload), pid)
    return ok(f"{len(rows)} medicamentos activos", data_refs=[r["id"] for r in rows])


def register_dose(con, payload):
    """Registra una toma (taken|skipped|snoozed) con auditoría e inventario.

    solo 'taken' descuenta stock, y solo si units_per_dose es calculable.
    """
    mid = payload.get("medication_id")
    status = payload.get("status")
    scheduled_at = payload.get("scheduled_at")
    if mid is None or status not in ("taken", "skipped", "snoozed"):
        return need(["medication_id", "status"], summary="medication_id y status(taken|skipped|snoozed) requeridos")
    if scheduled_at is None:
        scheduled_at = now_utc_iso()
    med = con.execute("SELECT * FROM medication WHERE id=?", (mid,)).fetchone()
    if med is None:
        return blocked(f"medicamento {mid} no existe")
    actor = payload.get("actor", "patient")
    cur = con.execute(
        "INSERT INTO medication_event (medication_id, scheduled_at, status, acted_at, actor) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(medication_id, scheduled_at) DO UPDATE SET status=excluded.status, "
        " acted_at=excluded.acted_at, actor=excluded.actor",
        (mid, scheduled_at, status, now_utc_iso(), actor),
    )
    if status == "taken" and med["units_per_dose"] is not None:
        upd = med["units_per_dose"]
        last = con.execute(
            "SELECT resulting_qty FROM medication_inventory WHERE medication_id=? "
            "ORDER BY id DESC LIMIT 1", (mid,),
        ).fetchone()
        qty = (last["resulting_qty"] if last else 0) - upd
        con.execute(
            "INSERT INTO medication_inventory (medication_id, delta, resulting_qty, reason, event_id, actor, created_at) "
            "VALUES (?, ?, ?, 'dose', ?, ?, ?)",
            (mid, -upd, qty, cur.lastrowid, actor, now_utc_iso()),
        )
    record(con, actor=actor, actor_role=payload.get("role", "patient"), action="dose.register",
           entity="medication_event", entity_id=cur.lastrowid, new_value={"status": status}, origin="user")
    con.commit()
    return ok(f"toma registrada: {status}", data_refs=[cur.lastrowid])
