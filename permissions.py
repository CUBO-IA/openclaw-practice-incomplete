"""Permisos por rol (acceso mínimo).

Roles: patient, caregiver, clinician, admin.
Regla de alcance: un 'patient' solo ve/actúa sobre su propio paciente; un
'caregiver' solo sobre el paciente que cuida (app_user.patient_id).
'clinician' y 'admin' pueden operar sobre cualquier paciente.
"""
from .errors import PermissionDenied

ROLES = ("patient", "caregiver", "clinician", "admin")

# Qué roles pueden ESCRIBIR cada tipo de entidad (el plan lo define el clínico).
WRITE_ROLES = {
    "appointment": ("clinician", "admin"),
    "medication": ("clinician", "admin"),
    "routine": ("clinician", "admin"),
    "care_plan": ("clinician", "admin"),
}

# Qué roles pueden LEER cada tipo de entidad.
READ_ROLES = {
    "appointment": ROLES,
    "medication": ROLES,
    "routine": ROLES,
    "care_plan": ROLES,
}


def assert_role(role, allowed):
    if role not in allowed:
        raise PermissionDenied(
            f"rol {role!r} no permitido (se requiere uno de {list(allowed)})"
        )


def check_scope(role, actor_patient_id, target_patient_id):
    """patient/caregiver solo sobre su propio paciente; clinician/admin sin límite."""
    if role in ("patient", "caregiver"):
        if actor_patient_id is None or target_patient_id != actor_patient_id:
            raise PermissionDenied(
                f"rol {role!r} fuera de alcance: paciente {target_patient_id} "
                f"no corresponde a su paciente {actor_patient_id}"
            )


def can_write(entity, role):
    return role in WRITE_ROLES.get(entity, ())


def can_read(entity, role):
    return role in READ_ROLES.get(entity, ROLES)
