"""Agentes de dominio: lógica determinista con contrato JSON estándar."""
from .response import ok, need, blocked, err  # noqa: F401
from .registry import dispatch  # noqa: F401
