"""Tick determinista de 60 s: dispara recordatorios vencidos vía Notifier.

Resistente a reinicios a mitad de tick: cada recordatorio se "reclama"
atómicamente (UPDATE ... WHERE status='scheduled'), así no se dispara dos veces.
No pasa por LLM.
"""
import json

from .audit import record
from .timeutil import parse_utc, now_utc_iso


class Tick:
    def __init__(self, con, notifier, channel="local"):
        self.con = con
        self.notifier = notifier
        self.channel = channel

    def run(self, now=None):
        """Procesa recordatorios programados cuyo fire_at <= now. Devuelve conteos."""
        now = now or parse_utc(now_utc_iso())
        now_s = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        due = self.con.execute(
            "SELECT r.*, p.display_name FROM reminder r\n"
            " JOIN patient p ON p.id = r.patient_id\n"
            " WHERE r.status='scheduled' AND r.fire_at <= ? ORDER BY r.fire_at",
            (now_s,),
        ).fetchall()
        fired = failed = 0
        for row in due:
            # Reclamo atómico: solo el que gana el UPDATE dispara el envío.
            claimed = self.con.execute(
                "UPDATE reminder SET status='fired', attempts=attempts+1\n"
                " WHERE id=? AND status='scheduled'", (row["id"],),
            )
            if claimed.rowcount == 0:
                continue  # otro proceso ya lo tomó
            msg = self._message(row)
            result = self.notifier.send(self.channel, f"patient:{row['patient_id']}", msg)
            if result.status in ("sent", "delivered"):
                self.con.execute(
                    "UPDATE reminder SET status='done', last_result=? WHERE id=? AND status='fired'",
                    (result.status, row["id"]),
                )
                fired += 1
            else:
                self.con.execute(
                    "UPDATE reminder SET status='failed', last_result=? WHERE id=? AND status='fired'",
                    (result.error or result.status, row["id"]),
                )
                failed += 1
            record(self.con, actor="tick", actor_role="system", action="reminder.fire",
                   entity="reminder", entity_id=row["id"],
                   new_value={"status": result.status, "kind": row["kind"]}, origin="system")
        return {"fired": fired, "failed": failed}

    def _message(self, row):
        kind = row["kind"]
        if kind == "appointment_24h":
            return "Recuerda: tienes una cita médica mañana. Revisa la app para detalles."
        if kind == "appointment_2h":
            return "Tu cita médica es en 2 horas."
        if kind == "medication":
            return "Hora de tu medicamento. Responde 1 Tomado · 2 Posponer · 3 Omitido"
        if kind == "exercise":
            return "Hora de tu actividad física. Responde 1 Hecho · 2 Parcial · 3 Omitido"
        return "Recordatorio de salud. Revisa la app."
