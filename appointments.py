"""Agente de citas: listar, crear, cancelar (determinista)."""
from ..core.audit import record
from ..core.repositories import AppointmentRepository, Actor
from .response import ok, need, blocked


def _actor(payload):
    return Actor(username=payload.get("actor", "agent"), role=payload.get("role", "clinician"),
                 patient_id=payload.get("actor_patient_id"))


def list_appointments(con, payload):
    pid = payload.get("patient_id")
    if pid is None:
        return need(["patient_id"])
    rows = AppointmentRepository(con).list_for_patient(_actor(payload), pid)
    return ok(f"{len(rows)} citas", data_refs=[r["id"] for r in rows])


def create_appointment(con, payload):
    pid = payload.get("patient_id")
    if pid is None:
        return need(["patient_id"])
    data = {k: payload[k] for k in payload if k in ("patient_id", "starts_at", "professional_id",
            "specialty", "center", "address", "reason", "status", "notes")}
    data.setdefault("patient_id", pid)
    if data.get("starts_at") in (None, ""):
        return need(["starts_at"])
    try:
        row = AppointmentRepository(con).create(_actor(payload), data)
    except Exception as e:  # validación/permisos
        return blocked(str(e))
    con.commit()
    return ok(f"cita {row['id']} creada", data_refs=[row["id"]])


def cancel_appointment(con, payload):
    aid = payload.get("appointment_id")
    if aid is None:
        return need(["appointment_id"])
    from ..core.reminders import ReminderGenerator
    try:
        row = AppointmentRepository(con).update_status(_actor(payload), aid, "cancelled",
                                                        reason=payload.get("reason"))
        ReminderGenerator(con).cancel_appointment(aid)
    except Exception as e:
        return blocked(str(e))
    con.commit()
    return ok(f"cita {aid} cancelada", data_refs=[aid])
