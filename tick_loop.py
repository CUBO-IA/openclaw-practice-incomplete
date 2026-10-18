"""Bucle determinista de 60 s: genera recordatorios y dispara los vencidos.

Uso: python -m caregiver.service.tick_loop [--db data/caregiver.db] [--interval 60]

- Aplica schema.sql si la BD no existe (solo tabla schema_meta ausente).
- Cada ciclo: genera recordatorios (citas/medicamentos/ejercicio) y corre el Tick.
- Registra una línea por ciclo en stdout (redirigida a data/tick.log por el launcher).
- Sin LLM; funciona sin internet.
"""
import argparse
import sys
import time
from pathlib import Path

from ..core.db import connect
from ..core.notifier import Notifier
from ..core.reminders import ReminderGenerator
from ..core.tick import Tick
from ..core.timeutil import now_utc_iso, parse_utc


def ensure_schema(con, schema_path):
    try:
        con.execute("SELECT 1 FROM schema_meta LIMIT 1")
    except Exception:
        con.executescript(Path(schema_path).read_text(encoding="utf-8"))
        con.commit()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tick_loop")
    ap.add_argument("--db", default="data/caregiver.db")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--once", action="store_true", help="ejecuta un solo ciclo y sale")
    a = ap.parse_args(argv)

    con = connect(a.db)
    schema = Path(a.db).resolve().parent.parent / "db" / "schema.sql"
    if not schema.exists():
        schema = Path(__file__).resolve().parent.parent.parent / "db" / "schema.sql"
    ensure_schema(con, schema)

    gen = ReminderGenerator(con)
    tick = Tick(con, Notifier())

    while True:
        try:
            now = parse_utc(now_utc_iso())
            gen.generate_appointments(now)
            gen.generate_medications(now)
            gen.generate_exercise(now)
            con.commit()
            result = tick.run(now)
            con.commit()
            print(f"{now_utc_iso()} cycle ok fired={result['fired']} failed={result['failed']}", flush=True)
        except Exception as e:
            con.rollback()
            print(f"{now_utc_iso()} cycle error: {e}", flush=True)
        if a.once:
            break
        time.sleep(a.interval)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
