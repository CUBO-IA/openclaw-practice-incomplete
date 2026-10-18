"""Validación con esquemas estrictos.

Regla: para operaciones sensibles no se aceptan campos desconocidos.
Devuelve lista de errores (vacía = válido).
"""

APPOINTMENT_STATUS = {"scheduled", "confirmed", "rescheduled", "cancelled", "attended", "missed_reported"}
MEDICATION_FREQUENCY = {"fixed", "prn", "variable"}
ROUTINE_STATUS = {"active", "under_review", "replaced"}

APPOINTMENT_FIELDS = {
    "patient_id", "plan_id", "starts_at", "professional_id", "specialty",
    "center", "address", "reason", "status", "cost", "notes", "dedup_key",
}
APPOINTMENT_REQUIRED = {"patient_id", "starts_at"}

MEDICATION_FIELDS = {
    "patient_id", "plan_id", "condition_id", "name", "presentation", "dose_text",
    "route", "frequency_type", "units_per_dose", "schedule_times", "instructions",
    "prescriber", "start_date", "end_date", "refill_lead_days", "critical_days", "active",
}
MEDICATION_REQUIRED = {"patient_id", "name", "frequency_type"}

ROUTINE_FIELDS = {
    "patient_id", "plan_id", "name", "start_date", "imported_interval_weeks",
    "review_interval_weeks", "review_due_date", "status",
}
ROUTINE_REQUIRED = {"patient_id", "name", "start_date"}


def _unknown(data, allowed):
    return sorted(set(data) - allowed)


def _missing(data, required):
    return sorted(k for k in required if data.get(k) in (None, ""))


def validate_appointment(data):
    errs = []
    u = _unknown(data, APPOINTMENT_FIELDS)
    if u:
        errs.append(f"campos desconocidos: {u}")
    for k in _missing(data, APPOINTMENT_REQUIRED):
        errs.append(f"falta campo obligatorio: {k}")
    if data.get("status") is not None and data.get("status") not in APPOINTMENT_STATUS:
        errs.append(f"status inválido: {data.get('status')!r}")
    return errs


def validate_medication(data):
    errs = []
    u = _unknown(data, MEDICATION_FIELDS)
    if u:
        errs.append(f"campos desconocidos: {u}")
    for k in _missing(data, MEDICATION_REQUIRED):
        errs.append(f"falta campo obligatorio: {k}")
    if data.get("frequency_type") is not None and data.get("frequency_type") not in MEDICATION_FREQUENCY:
        errs.append(f"frequency_type inválido: {data.get('frequency_type')!r}")
    return errs


def validate_routine(data):
    errs = []
    u = _unknown(data, ROUTINE_FIELDS)
    if u:
        errs.append(f"campos desconocidos: {u}")
    for k in _missing(data, ROUTINE_REQUIRED):
        errs.append(f"falta campo obligatorio: {k}")
    if data.get("status") is not None and data.get("status") not in ROUTINE_STATUS:
        errs.append(f"status inválido: {data.get('status')!r}")
    rw = data.get("review_interval_weeks")
    if rw is not None and not (6 <= rw <= 8):
        errs.append(f"review_interval_weeks fuera de rango (6-8): {rw!r}")
    return errs
