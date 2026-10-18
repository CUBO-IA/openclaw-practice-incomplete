"""Repositorios tipados con permisos y auditoría.

Cada mutación: valida -> aplica permiso -> ejecuta -> registra audit_event.
Las lecturas de listas "activas" ignoran los planes en borrador.
"""
from dataclasses import dataclass

from . import audit, validation
from .entities import Appointment, ExerciseItem, ExerciseRoutine, Medication
from .errors import NotFoundError, ValidationError
from .permissions import assert_role, can_read, can_write, check_scope


@dataclass(frozen=True)
class Actor:
    username: str
    role: str
    patient_id: int = None  # alcance para roles patient/caregiver


# ── helpers ────────────────────────────────────────────────────────────────

def _get(con, table, entity_id):
    row = con.execute(f"SELECT * FROM {table} WHERE id = ?", (entity_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"{table} id={entity_id} no existe")
    return row


def plan_is_confirmed(con, plan_id):
    if plan_id is None:
        return False
    row = con.execute("SELECT status FROM care_plan WHERE id = ?", (plan_id,)).fetchone()
    return bool(row and row["status"] == "confirmed")


def _audit(con, actor, action, entity, entity_id, old=None, new=None, reason=None):
    audit.record(con, actor=actor.username, actor_role=actor.role, action=action,
                 entity=entity, entity_id=entity_id, old_value=old, new_value=new,
                 reason=reason, origin="agent")


def _row_to_dict(row):
    return dict(row) if row is not None else None


# ── CarePlan ───────────────────────────────────────────────────────────────

class CarePlanRepository:
    def __init__(self, con):
        self.con = con

    def get(self, plan_id):
        return _get(self.con, "care_plan", plan_id)

    def create(self, actor, *, patient_id, version, session_date, professional_id,
               patient_present=0, caregiver_id=None, notes=None):
        assert_role(actor.role, ("clinician", "admin"))
        check_scope(actor.role, actor.patient_id, patient_id)
        cur = self.con.execute(
            "INSERT INTO care_plan (patient_id, version, status, session_date,\n"
            " professional_id, patient_present, caregiver_id, notes)\n"
            "VALUES (?, ?, 'draft', ?, ?, ?, ?, ?)",
            (patient_id, version, session_date, professional_id, patient_present,
             caregiver_id, notes),
        )
        pid = cur.lastrowid
        _audit(self.con, actor, "care_plan.create", "care_plan", pid,
               new={"patient_id": patient_id, "version": version, "status": "draft"})
        return self.get(pid)

    def confirm(self, actor, plan_id):
        """draft -> confirmed. Requiere profesional; registra confirmado y auditoría."""
        assert_role(actor.role, ("clinician", "admin"))
        row = self.get(plan_id)
        if row["status"] == "confirmed":
            return row  # idempotente
        if row["status"] != "draft":
            raise ValidationError([f"plan {plan_id} no está en borrador (status={row['status']})"])
        if row["professional_id"] is None:
            raise ValidationError(["no se puede confirmar un plan sin profesional"])
        from .timeutil import now_utc_iso
        self.con.execute(
            "UPDATE care_plan SET status='confirmed', confirmed_at=? WHERE id=? AND status='draft'",
            (now_utc_iso(), plan_id),
        )
        _audit(self.con, actor, "care_plan.confirm", "care_plan", plan_id,
               old={"status": "draft"}, new={"status": "confirmed"},
               reason="plan confirmado por el profesional")
        return self.get(plan_id)


# ── Appointments ───────────────────────────────────────────────────────────

class AppointmentRepository:
    def __init__(self, con):
        self.con = con

    def get(self, appt_id):
        return _get(self.con, "appointment", appt_id)

    def list_for_patient(self, actor, patient_id):
        if not can_read("appointment", actor.role):
            raise ValidationError([f"rol {actor.role} no puede leer citas"])
        check_scope(actor.role, actor.patient_id, patient_id)
        rows = self.con.execute(
            "SELECT * FROM appointment WHERE patient_id=? ORDER BY starts_at", (patient_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def create(self, actor, data):
        assert_role(actor.role, ("clinician", "admin"))
        errs = validation.validate_appointment(data)
        if errs:
            raise ValidationError(errs)
        check_scope(actor.role, actor.patient_id, data["patient_id"])
        cols = ["patient_id", "plan_id", "starts_at", "professional_id", "specialty",
                "center", "address", "reason", "status", "cost", "notes", "dedup_key"]
        cols = [c for c in cols if c in data]
        vals = [data[c] for c in cols]
        cur = self.con.execute(
            f"INSERT INTO appointment ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            vals,
        )
        aid = cur.lastrowid
        _audit(self.con, actor, "appointment.create", "appointment", aid, new=data)
        return self.get(aid)

    def update_status(self, actor, appt_id, new_status, reason=None):
        assert_role(actor.role, ("clinician", "admin"))
        if new_status not in validation.APPOINTMENT_STATUS:
            raise ValidationError([f"status inválido: {new_status!r}"])
        row = self.get(appt_id)
        check_scope(actor.role, actor.patient_id, row["patient_id"])
        self.con.execute(
            "UPDATE appointment SET status=? WHERE id=?", (new_status, appt_id),
        )
        _audit(self.con, actor, "appointment.update_status", "appointment", appt_id,
               old={"status": row["status"]}, new={"status": new_status}, reason=reason)
        return self.get(appt_id)


# ── Medications ────────────────────────────────────────────────────────────

class MedicationRepository:
    def __init__(self, con):
        self.con = con

    def get(self, med_id):
        return _get(self.con, "medication", med_id)

    def create(self, actor, data):
        assert_role(actor.role, ("clinician", "admin"))
        errs = validation.validate_medication(data)
        if errs:
            raise ValidationError(errs)
        check_scope(actor.role, actor.patient_id, data["patient_id"])
        cols = [c for c in validation.MEDICATION_FIELDS if c in data]
        vals = [data[c] for c in cols]
        cur = self.con.execute(
            f"INSERT INTO medication ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            vals,
        )
        mid = cur.lastrowid
        _audit(self.con, actor, "medication.create", "medication", mid, new=data)
        return self.get(mid)

    def list_active(self, actor, patient_id):
        """Medicamentos accionables: activos y con plan confirmado (borradores ignorados)."""
        if not can_read("medication", actor.role):
            raise ValidationError([f"rol {actor.role} no puede leer medicamentos"])
        check_scope(actor.role, actor.patient_id, patient_id)
        rows = self.con.execute(
            "SELECT m.* FROM medication m\n"
            " JOIN care_plan c ON c.id = m.plan_id\n"
            " WHERE m.patient_id=? AND m.active=1 AND c.status='confirmed'\n"
            " ORDER BY m.name", (patient_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


# ── Exercise routines ──────────────────────────────────────────────────────

class ExerciseRoutineRepository:
    def __init__(self, con):
        self.con = con

    def get(self, routine_id):
        return _get(self.con, "exercise_routine", routine_id)

    def create(self, actor, data):
        assert_role(actor.role, ("clinician", "admin"))
        errs = validation.validate_routine(data)
        if errs:
            raise ValidationError(errs)
        check_scope(actor.role, actor.patient_id, data["patient_id"])
        data = dict(data)
        data.setdefault("review_interval_weeks", 8)  # NOT NULL sin default en schema
        cols = [c for c in validation.ROUTINE_FIELDS if c in data]
        vals = [data[c] for c in cols]
        cur = self.con.execute(
            f"INSERT INTO exercise_routine ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            vals,
        )
        rid = cur.lastrowid
        _audit(self.con, actor, "exercise_routine.create", "exercise_routine", rid, new=data)
        return self.get(rid)

    def list_active(self, actor, patient_id):
        """Rutinas accionables: activas y con plan confirmado (borradores ignorados)."""
        if not can_read("routine", actor.role):
            raise ValidationError([f"rol {actor.role} no puede leer rutinas"])
        check_scope(actor.role, actor.patient_id, patient_id)
        rows = self.con.execute(
            "SELECT r.* FROM exercise_routine r\n"
            " JOIN care_plan c ON c.id = r.plan_id\n"
            " WHERE r.patient_id=? AND r.status='active' AND c.status='confirmed'\n"
            " ORDER BY r.name", (patient_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def add_item(self, actor, routine_id, *, name, days_of_week="[1,3,5]",
                 muscle_group=None, sets=None, reps=None, duration_min=None,
                 rest_sec=None, weight_kg=None, time_local=None, notes=None):
        assert_role(actor.role, ("clinician", "admin"))
        row = self.get(routine_id)
        check_scope(actor.role, actor.patient_id, row["patient_id"])
        cur = self.con.execute(
            "INSERT INTO exercise_item (routine_id, name, muscle_group, sets, reps,\n"
            " duration_min, rest_sec, weight_kg, days_of_week, time_local, notes)\n"
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (routine_id, name, muscle_group, sets, reps, duration_min, rest_sec,
             weight_kg, days_of_week, time_local, notes),
        )
        iid = cur.lastrowid
        _audit(self.con, actor, "exercise_item.create", "exercise_item", iid,
               new={"routine_id": routine_id, "name": name})
        return _get(self.con, "exercise_item", iid)
