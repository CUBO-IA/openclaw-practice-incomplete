"""Registro de agentes y acciones -> función (con, payload) -> response."""
from . import appointments, medications, exercise, records, connection, control
from .response import err


AGENTS = {
    "citas": {
        "list": appointments.list_appointments,
        "create": appointments.create_appointment,
        "cancel": appointments.cancel_appointment,
    },
    "medicamentos": {
        "list": medications.list_medications,
        "registrar_toma": medications.register_dose,
    },
    "ejercicio": {
        "list": exercise.list_routines,
        "registrar": exercise.register_event,
    },
    "registro": {
        "historial": records.history,
    },
    "conexion": {
        "contactos": connection.authorized_contacts,
    },
    "control": {
        "check": control.check,
    },
}


def dispatch(con, agent, action, payload):
    actions = AGENTS.get(agent)
    if actions is None:
        return err(f"agente desconocido: {agent}")
    fn = actions.get(action)
    if fn is None:
        return err(f"acción desconocida: {agent}.{action}")
    return fn(con, payload)
