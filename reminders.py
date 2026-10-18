"""Generador idempotente de recordatorios (reminder).

Citas: 24 h y 2 h antes (claves appt:{id}:24h y appt:{id}:2h).
Medicamentos: tomas de pauta fija de plan confirmado (clave med:{id}:{fecha}:{hora}).
Ejercicio: ítems de rutina activa con plan confirmado (clave ex:{item}:{fecha}:{hora}).
Todo determinista; sin LLM. La idempotencia se apoya en idempotency_key UNIQUE.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfoNotFoundError

from .timeutil import (now_utc_iso, parse_hhmm, parse_utc, utc_to_local, local_to_utc)
from .errors import NeedsInput


class ReminderGenerator:
    def __init__(self, con):
        self.con = con

    # ── upsert (solo inserte si no existe; si existe y está scheduled, actualiza fire_at) ──
    def _upsert_appointment(self, reminder):
        self.con.execute(
            "INSERT INTO reminder (patient_id, kind, entity_type, entity_id, fire_at,\n"
            " status, idempotency_key) VALUES (?, ?, 'appointment', ?, ?, 'scheduled', ?)\n"
            " ON CONFLICT(idempotency_key) DO UPDATE SET fire_at=excluded.fire_at,\n"
            "   status='scheduled', attempts=0",
            (reminder["patient_id"], reminder["kind"], reminder["entity_id"],
             reminder["fire_at"], reminder["key"]),
        )

    def _insert_if_missing(self, reminder):
        self.con.execute(
            "INSERT OR IGNORE INTO reminder (patient_id, kind, entity_type, entity_id,\n"
            " fire_at, status, idempotency_key) VALUES (?, ?, ?, ?, ?, 'scheduled', ?)",
            (reminder["patient_id"], reminder["kind"], reminder["entity_type"],
             reminder["entity_id"], reminder["fire_at"], reminder["key"]),
        )

    # ── Citas ─────────────────────────────────────────────────────────────
    def generate_appointments(self, now):
        """Para cada cita futura (scheduled/confirmed/rescheduled) con profesional,
        asegura recordatorios de 24 h y 2 h antes (si el fire_at aún es futuro)."""
        rows = self.con.execute(
            "SELECT a.*, p.timezone FROM appointment a\n"
            " JOIN patient p ON p.id = a.patient_id\n"
            " WHERE a.status IN ('scheduled','confirmed','rescheduled')\n"
            "   AND a.professional_id IS NOT NULL"
        ).fetchall()
        for row in rows:
            starts = parse_utc(row["starts_at"])
            for label, delta in (("24h", timedelta(hours=24)), ("2h", timedelta(hours=2))):
                fire = starts - delta
                if fire <= now:
                    continue
                self._upsert_appointment({
                    "patient_id": row["patient_id"],
                    "kind": f"appointment_{label}",
                    "entity_id": row["id"],
                    "fire_at": fire.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "key": f"appt:{row['id']}:{label}",
                })

    def cancel_appointment(self, appointment_id):
        """Cancela los recordatorios programados de una cita (cancelada/reprogramada)."""
        self.con.execute(
            "UPDATE reminder SET status='cancelled'\n"
            " WHERE entity_type='appointment' AND entity_id=? AND status='scheduled'",
            (appointment_id,),
        )

    # ── Medicamentos ──────────────────────────────────────────────────────
    def generate_medications(self, now, horizon_days=2):
        """Tomas de pauta fija de planes confirmados, dentro del horizonte.

        PRN y variable no generan recordatorios (stock/horario no calculable).
        """
        rows = self.con.execute(
            "SELECT m.*, p.timezone FROM medication m\n"
            " JOIN care_plan c ON c.id = m.plan_id\n"
            " JOIN patient p ON p.id = m.patient_id\n"
            " WHERE m.active=1 AND c.status='confirmed'\n"
            "   AND m.frequency_type='fixed' AND m.schedule_times IS NOT NULL"
        ).fetchall()
        for row in rows:
            try:
                times = json.loads(row["schedule_times"])
                local_date = utc_to_local(now, row["timezone"]).date()
            except (ValueError, TypeError, ZoneInfoNotFoundError):
                continue  # pauta o zona inválida: no genera; la detecta el control
            for d in range(horizon_days):
                day = local_date + timedelta(days=d)
                for t in times:
                    fire = local_to_utc(
                        datetime.combine(day, parse_hhmm(t)),
                        row["timezone"],
                    )
                    if fire <= now:
                        continue
                    self._insert_if_missing({
                        "patient_id": row["patient_id"],
                        "kind": "medication",
                        "entity_type": "medication",
                        "entity_id": row["id"],
                        "fire_at": fire.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "key": f"med:{row['id']}:{day}:{t}",
                    })

    # ── Ejercicio ─────────────────────────────────────────────────────────
    def generate_exercise(self, now, horizon_days=7):
        """Ítems de rutina activa con plan confirmado, en sus días y hora local."""
        rows = self.con.execute(
            "SELECT ei.*, er.patient_id, p.timezone FROM exercise_item ei\n"
            " JOIN exercise_routine er ON er.id = ei.routine_id\n"
            " JOIN care_plan c ON c.id = er.plan_id\n"
            " JOIN patient p ON p.id = er.patient_id\n"
            " WHERE er.status='active' AND c.status='confirmed'\n"
            "   AND ei.days_of_week IS NOT NULL AND ei.time_local IS NOT NULL"
        ).fetchall()
        for row in rows:
            try:
                dow = set(json.loads(row["days_of_week"]))
                local_date = utc_to_local(now, row["timezone"]).date()
                t = parse_hhmm(row["time_local"])
            except (ValueError, TypeError, ZoneInfoNotFoundError):
                continue
            for d in range(horizon_days):
                day = local_date + timedelta(days=d)
                if day.isoweekday() not in dow:
                    continue
                fire = local_to_utc(datetime.combine(day, t), row["timezone"])
                if fire <= now:
                    continue
                self._insert_if_missing({
                    "patient_id": row["patient_id"],
                    "kind": "exercise",
                    "entity_type": "exercise_item",
                    "entity_id": row["id"],
                    "fire_at": fire.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "key": f"ex:{row['id']}:{day}:{row['time_local']}",
                })
