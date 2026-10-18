"""Agente de conexión con cuidador: destinatarios autorizados (determinista)."""
from .response import ok, blocked


def authorized_contacts(con, payload):
    pid = payload.get("patient_id")
    if pid is None:
        return blocked("patient_id requerido")
    rows = con.execute(
        "SELECT cc.owner_type, cc.owner_id, cc.channel, cc.address, cg.name "
        "FROM contact_channel cc "
        "LEFT JOIN caregiver cg ON cc.owner_type='caregiver' AND cg.id=cc.owner_id "
        "WHERE (cc.owner_type='patient' AND cc.owner_id=?) "
        "   OR (cc.owner_type='caregiver' AND cg.patient_id=?) "
        "AND cc.consent_at IS NOT NULL AND cc.consent_revoked_at IS NULL",
        (pid, pid),
    ).fetchall()
    if not rows:
        return blocked("sin contacto autorizado con consentimiento vigente")
    return ok(f"{len(rows)} contactos autorizados",
              data_refs=[r["channel"] + ":" + str(r["address"]) for r in rows])
