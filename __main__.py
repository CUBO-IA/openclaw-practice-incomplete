"""CLI mínimo y determinista: python -m caregiver <comando> --json '<payload>'

Salida JSON con el contrato estándar:
  {"status": "success|needs_input|blocked|error", "summary": ..., "data_refs": [...]}
Nada de esto usa LLM.
"""
import argparse
import json
import sys

from .core import Database
from .core.errors import CaregiverError, PermissionDenied, ValidationError, NotFoundError
from .agents.registry import dispatch
from .agents import inbound


def _emit(status, summary="", **extra):
    out = {"status": status, "summary": summary}
    out.update(extra)
    print(json.dumps(out, ensure_ascii=False, default=str))


def _actor(args):
    from .core.repositories import Actor
    return Actor(username=args.actor, role=args.role, patient_id=args.patient_id)


def cmd_appointment_list(con, args):
    from .core.repositories import AppointmentRepository
    repo = AppointmentRepository(con)
    rows = repo.list_for_patient(_actor(args), args.patient_id)
    _emit("success", f"{len(rows)} citas", data_refs=[r["id"] for r in rows])


def cmd_appointment_create(con, args):
    from .core.repositories import AppointmentRepository
    data = json.loads(args.json)
    repo = AppointmentRepository(con)
    row = repo.create(_actor(args), data)
    con.commit()
    _emit("success", f"cita {row['id']} creada", data_refs=[row["id"]])


def cmd_medication_list(con, args):
    from .core.repositories import MedicationRepository
    repo = MedicationRepository(con)
    rows = repo.list_active(_actor(args), args.patient_id)
    _emit("success", f"{len(rows)} medicamentos activos", data_refs=[r["id"] for r in rows])


def cmd_routine_list(con, args):
    from .core.repositories import ExerciseRoutineRepository
    repo = ExerciseRoutineRepository(con)
    rows = repo.list_active(_actor(args), args.patient_id)
    _emit("success", f"{len(rows)} rutinas activas", data_refs=[r["id"] for r in rows])


def cmd_agent(con, args):
    """python -m caregiver <agente> <acción> --json '<payload>'"""
    payload = json.loads(args.json) if args.json else {}
    payload.setdefault("actor", args.actor)
    payload.setdefault("role", args.role)
    res = dispatch(con, args.agent, args.action, payload)
    print(json.dumps(res, ensure_ascii=False, default=str))


def cmd_inbound(con, args):
    payload = json.loads(args.json)
    res = inbound.handle(con, chat_id=payload.get("chat_id"), text=payload.get("text", ""))
    print(json.dumps(res, ensure_ascii=False, default=str))


def build_parser():
    p = argparse.ArgumentParser(prog="caregiver", description="Caregiver Agent — núcleo determinista")
    p.add_argument("--db", default="data/caregiver.db")
    p.add_argument("--actor", default="admin_demo")
    p.add_argument("--role", default="admin")
    p.add_argument("--patient-id", type=int, default=None)
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("appointment-list")
    a.set_defaults(fn=cmd_appointment_list)
    a = sub.add_parser("appointment-create")
    a.add_argument("--json", required=True)
    a.set_defaults(fn=cmd_appointment_create)
    a = sub.add_parser("medication-list")
    a.set_defaults(fn=cmd_medication_list)
    a = sub.add_parser("routine-list")
    a.set_defaults(fn=cmd_routine_list)

    # dispatch genérico: <agente> <acción>
    a = sub.add_parser("agent")
    a.add_argument("agent")
    a.add_argument("action")
    a.add_argument("--json", default="{}")
    a.set_defaults(fn=cmd_agent)

    # mensajes entrantes
    a = sub.add_parser("inbound")
    a.add_argument("--json", required=True)
    a.set_defaults(fn=cmd_inbound)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        with Database(args.db) as db:
            con = db.con
            if args.patient_id is None and args.role in ("patient", "caregiver"):
                _emit("error", "patient_id requerido para rol patient/caregiver")
                return 1
            args.fn(con, args)
        return 0
    except (PermissionDenied, ValidationError, NotFoundError, CaregiverError) as e:
        _emit("blocked", str(e))
        return 1
    except json.JSONDecodeError as e:
        _emit("error", f"payload JSON inválido: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
