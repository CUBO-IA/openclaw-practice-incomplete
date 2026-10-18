"""Agente de ejercicio: listar rutinas y registrar evento."""
from ..core.audit import record
from ..core.repositories import ExerciseRoutineRepository, Actor
from ..core.timeutil import now_utc_iso
from .response import ok, need, blocked


def _actor(payload):
    return Actor(username=payload.get("actor", "agent"), role=payload.get("role", "clinician"),
                 patient_id=payload.get("actor_patient_id"))


def list_routines(con, payload):
    pid = payload.get("patient_id")
    if pid is None:
        return need(["patient_id"])
    rows = ExerciseRoutineRepository(con).list_active(_actor(payload), pid)
    return ok(f"{len(rows)} rutinas activas", data_refs=[r["id"] for r in rows])


def register_event(con, payload):
    rid = payload.get("routine_id")
    status = payload.get("status")
    if rid is None or status not in ("completed", "partial", "skipped", "snoozed"):
        return need(["routine_id", "status"])
    cur = con.execute(
        "INSERT INTO exercise_event (routine_id, scheduled_at, status, duration_min, acted_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(routine_id, scheduled_at) DO UPDATE SET status=excluded.status",
        (rid, payload.get("scheduled_at") or now_utc_iso(), status,
         payload.get("duration_min"), now_utc_iso()),
    )
    record(con, actor=payload.get("actor", "patient"), actor_role="patient", action="exercise.register",
           entity="exercise_event", entity_id=cur.lastrowid, new_value={"status": status}, origin="user")
    con.commit()
    return ok(f"evento registrado: {status}", data_refs=[cur.lastrowid])
