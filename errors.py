"""Excepciones de dominio del núcleo (Caregiver Agent)."""


class CaregiverError(Exception):
    """Base para todos los errores del dominio."""


class ValidationError(CaregiverError):
    def __init__(self, errors):
        self.errors = list(errors) if not isinstance(errors, str) else [errors]
        super().__init__("; ".join(self.errors))


class NotFoundError(CaregiverError):
    pass


class PermissionDenied(CaregiverError):
    pass


class NeedsInput(CaregiverError):
    def __init__(self, missing):
        self.missing = list(missing) if not isinstance(missing, str) else [missing]
        super().__init__("Faltan datos: " + ", ".join(self.missing))
