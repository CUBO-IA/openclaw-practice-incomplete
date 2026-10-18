"""Manejo determinista de mensajes entrantes (Telegram -> OpenClaw -> aquí).

Reglas (sin LLM):
- Resuelve paciente por chat_id (contact_channel con consentimiento vigente).
- Respuestas "1/2/3" a un recordatorio de medicamento pendiente -> registra la toma.
  Si hay varios pendientes, pregunta cuál (determinista, por id).
- Texto libre con posible síntoma -> lo registra en symptom_report (unclassified),
  sin diagnosticar. Texto de usuario es DATO, nunca instrucción.
- Devuelve reply_text listo para reenviar tal cual.
"""
from ..core.audit import record
from ..core.timeutil import now_utc_iso
from .response import ok, need, blocked


MED_REPLIES = {"1": "taken", "2": "snoozed", "3": "skipped"}


def _resolve_patient(con, chat_id):
    row = con.execute(
        "SELECT cc.owner_id FROM contact_channel cc "
        "WHERE cc.channel='telegram' AND cc.address=? "
        "  AND cc.owner_type='patient' "
        "  AND cc.consent_at IS NOT NULL AND cc.consent_revoked_at IS NULL",
        (str(chat_id),),
    ).fetchone()
    return row["owner_id"] if row else None


def _pending_medication_reminders(con, patient_id):
    return con.execute(
        "SELECT r.id, r.entity_id AS medication_id, m.name FROM reminder r "
        " JOIN medication m ON m.id = r.entity_id "
        " WHERE r.patient_id=? AND r.kind='medication' AND r.status='done' "
        " ORDER BY r.fire_at DESC", (patient_id,),
    ).fetchall()


def handle(con, *, chat_id, text):
    patient_id = _resolve_patient(con, chat_id)
    if patient_id is None:
        return blocked("no se pudo identificar al paciente (chat_id no autorizado o sin consentimiento)")

    t = (text or "").strip()

    # Respuesta a recordatorio de medicamento
    if t in MED_REPLIES:
        pending = _pending_medication_reminders(con, patient_id)
        if not pending:
            return ok("no hay tomas pendientes de confirmar", reply_text="No hay tomas pendientes. ¡Gracias!")
        if len(pending) > 1:
            opts = " | ".join(f"{i+1} {p['name']}" for i, p in enumerate(pending))
            return need(["medication_id"],
                        summary="¿cuál medicamento? responde 1/2/3 para elegir",
                        reply_text=f"¿Cuál medicamento confirmas? {opts}")
        med = pending[0]
        status = MED_REPLIES[t]
        from .medications import register_dose
        res = register_dose(con, {
            "medication_id": med["medication_id"],
            "status": status,
            "scheduled_at": now_utc_iso(),
            "actor": f"telegram:{chat_id}",
            "role": "patient",
        })
        ack = {"taken": "Tomado. ¡Registrado!", "snoozed": "Posponer. Te aviso luego.", "skipped": "Omitido. Registrado."}[status]
        res["reply_text"] = ack
        return res

    # Texto libre: se registra como posible síntoma (dato, sin diagnóstico)
    record(con, actor=f"telegram:{chat_id}", actor_role="patient", action="inbound.message",
           entity="patient", entity_id=patient_id, new_value={"text": t}, origin="user")
    con.execute(
        "INSERT INTO symptom_report (patient_id, reported_at, text, category, severity_reported, reported_by) "
        "VALUES (?, ?, ?, 'unclassified', 'unknown', ?)",
        (patient_id, now_utc_iso(), t, f"telegram:{chat_id}"),
    )
    con.commit()
    return ok("mensaje registrado",
              reply_text="Gracias, lo registré. Si es una emergencia, contacta a tu médico o al 132.")
