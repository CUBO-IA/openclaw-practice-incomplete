"""Entidades tipadas (dataclasses) del núcleo."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Appointment:
    id: Optional[int]
    patient_id: int
    starts_at: str
    professional_id: Optional[int] = None
    plan_id: Optional[int] = None
    specialty: Optional[str] = None
    center: Optional[str] = None
    address: Optional[str] = None
    reason: Optional[str] = None
    status: str = "scheduled"
    cost: Optional[float] = None
    notes: Optional[str] = None
    dedup_key: Optional[str] = None


@dataclass(frozen=True)
class Medication:
    id: Optional[int]
    patient_id: int
    name: str
    frequency_type: str
    plan_id: Optional[int] = None
    condition_id: Optional[int] = None
    presentation: Optional[str] = None
    dose_text: Optional[str] = None
    route: Optional[str] = None
    units_per_dose: Optional[float] = None
    schedule_times: Optional[str] = None
    instructions: Optional[str] = None
    prescriber: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    refill_lead_days: int = 10
    critical_days: int = 3
    active: int = 1


@dataclass(frozen=True)
class ExerciseRoutine:
    id: Optional[int]
    patient_id: int
    name: str
    start_date: str
    plan_id: Optional[int] = None
    imported_interval_weeks: Optional[int] = None
    review_interval_weeks: int = 8
    review_due_date: Optional[str] = None
    status: str = "active"


@dataclass(frozen=True)
class ExerciseItem:
    id: Optional[int]
    routine_id: int
    name: str
    muscle_group: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_min: Optional[int] = None
    rest_sec: Optional[int] = None
    weight_kg: Optional[float] = None
    days_of_week: str = "[1,3,5]"
    time_local: Optional[str] = None
    notes: Optional[str] = None
