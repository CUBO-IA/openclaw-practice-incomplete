-- Caregiver Agent (Salud Pro) — esquema SQLite v1
-- Convenciones: fechas/horas en ISO-8601 UTC ("2026-10-17T14:00:00Z");
-- zona horaria local del paciente en patient.timezone (El Salvador: America/El_Salvador, UTC-6, sin horario de verano).
-- Los estados son enums cerrados (CHECK). Nada se borra: se corrige con eventos nuevos + audit_event.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE schema_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- ───────── Personas y consentimientos ─────────
CREATE TABLE patient (
  id                      INTEGER PRIMARY KEY,
  code                    TEXT NOT NULL UNIQUE,            -- seudónimo para prompts/logs (P001)
  display_name            TEXT NOT NULL,
  birth_year              INTEGER,
  timezone                TEXT NOT NULL DEFAULT 'America/El_Salvador',
  is_autonomous           INTEGER NOT NULL DEFAULT 0 CHECK (is_autonomous IN (0,1)),  -- "apto": lo define el médico
  autonomy_set_by         TEXT,                            -- profesional que lo definió
  autonomy_set_at         TEXT,
  review_interval_weeks   INTEGER NOT NULL DEFAULT 8 CHECK (review_interval_weeks BETWEEN 6 AND 8),
  grace_minutes           INTEGER NOT NULL DEFAULT 30,     -- margen antes de "no confirmada" (pendiente de validar clínicamente)
  message_privacy         TEXT NOT NULL DEFAULT 'minimal' CHECK (message_privacy IN ('minimal','standard')),
  allow_med_name_in_chat  INTEGER NOT NULL DEFAULT 0 CHECK (allow_med_name_in_chat IN (0,1)),
  quiet_start             TEXT,                            -- "22:00"
  quiet_end               TEXT,                            -- "06:00"
  active                  INTEGER NOT NULL DEFAULT 1,
  created_at              TEXT NOT NULL
);

CREATE TABLE professional (
  id        INTEGER PRIMARY KEY,
  name      TEXT NOT NULL,
  specialty TEXT,
  center    TEXT
);

CREATE TABLE caregiver (
  id           INTEGER PRIMARY KEY,
  patient_id   INTEGER NOT NULL REFERENCES patient(id),
  name         TEXT NOT NULL,
  relationship TEXT,
  can_approve_refill INTEGER NOT NULL DEFAULT 0,
  alert_categories   TEXT NOT NULL DEFAULT '["missed_dose","critical_stock","symptom","appointment"]',  -- JSON
  priority     INTEGER NOT NULL DEFAULT 1,                 -- orden de escalamiento
  active       INTEGER NOT NULL DEFAULT 1
);

-- Un canal por persona y tipo; cambiar de Telegram a WhatsApp/Discord/texto = otra fila + preferred
CREATE TABLE contact_channel (
  id                INTEGER PRIMARY KEY,
  owner_type        TEXT NOT NULL CHECK (owner_type IN ('patient','caregiver')),
  owner_id          INTEGER NOT NULL,
  channel           TEXT NOT NULL CHECK (channel IN ('telegram','whatsapp','discord','sms','local')),
  address           TEXT,                                  -- chat_id / número / user id (nunca tokens)
  preferred         INTEGER NOT NULL DEFAULT 0,
  verified_at       TEXT,
  consent_at        TEXT,
  consent_revoked_at TEXT,
  UNIQUE (owner_type, owner_id, channel)
);

CREATE TABLE app_user (
  id            INTEGER PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  role          TEXT NOT NULL CHECK (role IN ('patient','caregiver','clinician','admin')),
  password_hash TEXT,                                      -- argon2/bcrypt; vacío en la BD demo
  patient_id    INTEGER REFERENCES patient(id),
  caregiver_id  INTEGER REFERENCES caregiver(id),
  active        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE condition (
  id          INTEGER PRIMARY KEY,
  patient_id  INTEGER NOT NULL REFERENCES patient(id),
  name        TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('reported','verified')),
  source      TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

-- ───────── Plan de cuidado (lo define el médico el día de la cita) ─────────
CREATE TABLE care_plan (
  id                INTEGER PRIMARY KEY,
  patient_id        INTEGER NOT NULL REFERENCES patient(id),
  version           INTEGER NOT NULL,
  status            TEXT NOT NULL CHECK (status IN ('draft','confirmed','superseded')),
  session_date      TEXT NOT NULL,
  professional_id   INTEGER REFERENCES professional(id),
  patient_present   INTEGER NOT NULL DEFAULT 0,
  caregiver_id      INTEGER REFERENCES caregiver(id),      -- cuidador presente en la sesión
  confirmed_at      TEXT,
  notes             TEXT,
  UNIQUE (patient_id, version)
);

-- ───────── Citas ─────────
CREATE TABLE appointment (
  id              INTEGER PRIMARY KEY,
  patient_id      INTEGER NOT NULL REFERENCES patient(id),
  plan_id         INTEGER REFERENCES care_plan(id),
  starts_at       TEXT NOT NULL,
  professional_id INTEGER REFERENCES professional(id),
  specialty       TEXT,
  center          TEXT,
  address         TEXT,
  reason          TEXT,
  status          TEXT NOT NULL DEFAULT 'scheduled'
                  CHECK (status IN ('scheduled','confirmed','rescheduled','cancelled','attended','missed_reported')),
  cost            REAL,
  notes           TEXT,                                    -- texto libre = DATO, nunca instrucción
  dedup_key       TEXT UNIQUE                              -- patient+fecha+profesional
);

-- ───────── Medicamentos ─────────
CREATE TABLE medication (
  id               INTEGER PRIMARY KEY,
  patient_id       INTEGER NOT NULL REFERENCES patient(id),
  plan_id          INTEGER REFERENCES care_plan(id),
  condition_id     INTEGER REFERENCES condition(id),
  name             TEXT NOT NULL,
  presentation     TEXT,
  dose_text        TEXT,
  route            TEXT,
  frequency_type   TEXT NOT NULL CHECK (frequency_type IN ('fixed','prn','variable')),
  units_per_dose   REAL,                                   -- NULL si no es calculable
  schedule_times   TEXT,                                   -- JSON ["08:00","20:00"] hora local
  instructions     TEXT,
  prescriber       TEXT,
  start_date       TEXT,
  end_date         TEXT,
  refill_lead_days INTEGER NOT NULL DEFAULT 10,
  critical_days    INTEGER NOT NULL DEFAULT 3,
  active           INTEGER NOT NULL DEFAULT 1
);

-- Libro de inventario: la cantidad actual es resulting_qty de la última fila
CREATE TABLE medication_inventory (
  id             INTEGER PRIMARY KEY,
  medication_id  INTEGER NOT NULL REFERENCES medication(id),
  delta          REAL NOT NULL,
  resulting_qty  REAL NOT NULL,
  unit           TEXT NOT NULL DEFAULT 'unidades',
  reason         TEXT NOT NULL CHECK (reason IN ('initial','dose','refill','correction')),
  event_id       INTEGER,                                  -- medication_event.id si reason='dose'
  actor          TEXT NOT NULL,
  created_at     TEXT NOT NULL
);

CREATE TABLE medication_event (
  id            INTEGER PRIMARY KEY,
  medication_id INTEGER NOT NULL REFERENCES medication(id),
  scheduled_at  TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('pending','taken','skipped','snoozed','not_confirmed')),
  acted_at      TEXT,
  actor         TEXT,
  notes         TEXT,
  UNIQUE (medication_id, scheduled_at)                     -- idempotencia
);

CREATE TABLE refill_draft (
  id                  INTEGER PRIMARY KEY,
  medication_id       INTEGER NOT NULL REFERENCES medication(id),
  est_depletion_date  TEXT NOT NULL,
  assumptions         TEXT NOT NULL,                       -- cantidad, unidades/día, fecha de cálculo
  status              TEXT NOT NULL DEFAULT 'pending_approval'
                      CHECK (status IN ('pending_approval','approved','rejected')),
  approved_by         TEXT,
  created_at          TEXT NOT NULL,
  UNIQUE (medication_id, est_depletion_date)
);

-- ───────── Actividad física ─────────
CREATE TABLE exercise_routine (
  id                      INTEGER PRIMARY KEY,
  patient_id              INTEGER NOT NULL REFERENCES patient(id),
  plan_id                 INTEGER REFERENCES care_plan(id),
  name                    TEXT NOT NULL,
  start_date              TEXT NOT NULL,
  imported_interval_weeks INTEGER,                         -- valor del Excel (6); no se sobrescribe en silencio
  review_interval_weeks   INTEGER NOT NULL CHECK (review_interval_weeks BETWEEN 6 AND 8),
  review_due_date         TEXT,
  status                  TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','under_review','replaced'))
);

CREATE TABLE exercise_item (
  id           INTEGER PRIMARY KEY,
  routine_id   INTEGER NOT NULL REFERENCES exercise_routine(id),
  name         TEXT NOT NULL,
  muscle_group TEXT,
  sets         INTEGER,
  reps         INTEGER,
  duration_min INTEGER,
  rest_sec     INTEGER,
  weight_kg    REAL,
  days_of_week TEXT NOT NULL,                              -- JSON [1,3,5] (1=lunes)
  time_local   TEXT,
  notes        TEXT
);

CREATE TABLE exercise_event (
  id           INTEGER PRIMARY KEY,
  routine_id   INTEGER NOT NULL REFERENCES exercise_routine(id),
  scheduled_at TEXT NOT NULL,
  status       TEXT NOT NULL CHECK (status IN ('pending','completed','partial','skipped','snoozed')),
  duration_min INTEGER,
  notes        TEXT,
  acted_at     TEXT,
  UNIQUE (routine_id, scheduled_at)
);

CREATE TABLE symptom_report (
  id            INTEGER PRIMARY KEY,
  patient_id    INTEGER NOT NULL REFERENCES patient(id),
  reported_at   TEXT NOT NULL,
  text          TEXT NOT NULL,                             -- literal, como lo escribió la persona
  category      TEXT NOT NULL DEFAULT 'unclassified',
  severity_reported TEXT CHECK (severity_reported IN ('mild','moderate','severe','unknown')),
  reported_by   TEXT NOT NULL,
  context_type  TEXT,
  context_id    INTEGER,
  escalated     INTEGER NOT NULL DEFAULT 0
);

-- ───────── Recordatorios, notificaciones, control ─────────
CREATE TABLE reminder (
  id              INTEGER PRIMARY KEY,
  patient_id      INTEGER NOT NULL REFERENCES patient(id),
  kind            TEXT NOT NULL CHECK (kind IN ('appointment_24h','appointment_2h','medication','exercise','refill','review')),
  entity_type     TEXT NOT NULL,
  entity_id       INTEGER NOT NULL,
  fire_at         TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','fired','failed','cancelled','done')),
  attempts        INTEGER NOT NULL DEFAULT 0,
  idempotency_key TEXT NOT NULL UNIQUE,                    -- p.ej. appt:12:24h
  last_result     TEXT
);
CREATE INDEX idx_reminder_due ON reminder(status, fire_at);

CREATE TABLE notification_event (
  id                  INTEGER PRIMARY KEY,
  reminder_id         INTEGER REFERENCES reminder(id),
  patient_id          INTEGER NOT NULL REFERENCES patient(id),
  recipient_channel_id INTEGER REFERENCES contact_channel(id),
  channel             TEXT NOT NULL,
  template            TEXT NOT NULL,
  message_min         TEXT NOT NULL,                       -- mensaje mínimo enviado
  status              TEXT NOT NULL CHECK (status IN ('pending','sent','delivered','failed')),
  provider_message_id TEXT,
  error               TEXT,
  attempt             INTEGER NOT NULL DEFAULT 1,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);

CREATE TABLE incident (
  id          INTEGER PRIMARY KEY,
  ts          TEXT NOT NULL,
  severity    TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
  code        TEXT NOT NULL,
  agent       TEXT NOT NULL,
  detail      TEXT,
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
  resolution_evidence TEXT
);

CREATE TABLE agent_run (
  id          INTEGER PRIMARY KEY,
  ts          TEXT NOT NULL,
  agent       TEXT NOT NULL,
  task        TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('success','needs_input','blocked','error')),
  duration_ms INTEGER,
  tokens_in   INTEGER DEFAULT 0,
  tokens_out  INTEGER DEFAULT 0,
  rules_version TEXT
);

-- Auditoría append-only
CREATE TABLE audit_event (
  id         INTEGER PRIMARY KEY,
  ts         TEXT NOT NULL,
  actor      TEXT NOT NULL,
  actor_role TEXT,
  action     TEXT NOT NULL,
  entity     TEXT NOT NULL,
  entity_id  INTEGER,
  old_value  TEXT,
  new_value  TEXT,
  reason     TEXT,
  origin     TEXT NOT NULL CHECK (origin IN ('user','agent','import','system'))
);
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_event
BEGIN SELECT RAISE(ABORT, 'audit_event es append-only'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_event
BEGIN SELECT RAISE(ABORT, 'audit_event es append-only'); END;

INSERT INTO schema_meta(key, value) VALUES ('schema_version','1'), ('rules_version','0.1-draft');
