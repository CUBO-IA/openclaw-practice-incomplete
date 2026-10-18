"""Contrato JSON estándar de respuesta de agente (OPENCLAW_PROMPT.md §4)."""


def response(status, summary="", *, data_refs=None, actions_proposed=None,
             actions_completed=None, alerts=None, missing_data=None,
             audit_event_required=True, **extra):
    out = {
        "status": status,
        "summary": (summary or "")[:200],
        "data_refs": list(data_refs or []),
        "actions_proposed": list(actions_proposed or []),
        "actions_completed": list(actions_completed or []),
        "alerts": list(alerts or []),
        "missing_data": list(missing_data or []),
        "audit_event_required": bool(audit_event_required),
    }
    out.update(extra)
    return out


def ok(summary="", **kw):
    return response("success", summary, **kw)


def need(missing, summary="faltan datos", **kw):
    return response("needs_input", summary, missing_data=list(missing), **kw)


def blocked(summary="", **kw):
    return response("blocked", summary, **kw)


def err(summary="", **kw):
    return response("error", summary, **kw)
