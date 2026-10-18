"""Exporta calendar.ics con VALARM desde citas confirmadas/programadas."""
from datetime import timedelta

from .timeutil import parse_utc


def _ical_dt(iso_utc):
    return parse_utc(iso_utc).strftime("%Y%m%dT%H%M%SZ")


def escape(text):
    if text is None:
        return ""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
                .replace("\n", "\\n"))


def build_calendar(con, patient_id, title="Salud Pro"):
    """Construye el contenido .ics para las citas futuras del paciente."""
    rows = con.execute(
        "SELECT a.*, pr.name AS prof_name, pr.center FROM appointment a\n"
        " LEFT JOIN professional pr ON pr.id = a.professional_id\n"
        " WHERE a.patient_id=? AND a.status IN ('scheduled','confirmed','rescheduled')\n"
        " ORDER BY a.starts_at", (patient_id,),
    ).fetchall()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Caregiver Agent//Salud Pro//ES",
        "CALSCALE:GREGORIAN",
    ]
    for row in rows:
        starts = parse_utc(row["starts_at"])
        uid = f"appt-{row['id']}@saludpro.local"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_ical_dt(row['starts_at'])}",
            f"DTSTART:{_ical_dt(row['starts_at'])}",
            f"SUMMARY:{escape(row['reason'] or 'Cita médica')}",
            f"LOCATION:{escape(row['center'] or '')}",
            f"DESCRIPTION:{escape((row['prof_name'] or '') + (' · ' + row['reason'] if row['reason'] else ''))}",
        ]
        # VALARM: 24 h y 2 h antes
        for label, hours in (("24H", 24), ("2H", 2)):
            lines += [
                "BEGIN:VALARM",
                f"ACTION:DISPLAY",
                f"TRIGGER:-PT{hours}H",
                f"DESCRIPTION:Recordatorio de cita",
                f"END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
