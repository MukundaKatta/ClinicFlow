"""Utility helpers for ClinicFlow.

Time slot generation, conflict detection, and schedule formatting.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def generate_time_slots(
    start: str,
    end: str,
    interval_minutes: int = 15,
    date: str | None = None,
) -> list[dict[str, str]]:
    """Generate time slots between *start* and *end* times.

    Parameters
    ----------
    start : str
        Start time in ``"HH:MM"`` format.
    end : str
        End time in ``"HH:MM"`` format.
    interval_minutes : int
        Length of each slot in minutes.
    date : str | None
        Optional date string (``"YYYY-MM-DD"``) to attach to every slot.

    Returns
    -------
    list[dict[str, str]]
        Each dict has ``"start"`` and ``"end"`` keys in ``"HH:MM"`` format,
        plus ``"date"`` when *date* is provided.
    """
    base = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    delta = timedelta(minutes=interval_minutes)

    slots: list[dict[str, str]] = []
    current = base
    while current + delta <= end_dt:
        slot: dict[str, str] = {
            "start": current.strftime("%H:%M"),
            "end": (current + delta).strftime("%H:%M"),
        }
        if date:
            slot["date"] = date
        slots.append(slot)
        current += delta

    return slots


def check_overlap(
    start_a: datetime,
    duration_a: int,
    start_b: datetime,
    duration_b: int,
) -> bool:
    """Return ``True`` if two time ranges overlap.

    Parameters
    ----------
    start_a, start_b : datetime
        Start times of the two ranges.
    duration_a, duration_b : int
        Durations in minutes.
    """
    end_a = start_a + timedelta(minutes=duration_a)
    end_b = start_b + timedelta(minutes=duration_b)
    return start_a < end_b and start_b < end_a


def detect_conflicts(
    proposed_start: datetime,
    proposed_duration: int,
    existing_appointments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find existing appointments that conflict with a proposed time.

    Parameters
    ----------
    proposed_start : datetime
        Proposed appointment start.
    proposed_duration : int
        Proposed duration in minutes.
    existing_appointments : list[dict]
        Each dict must have ``"start"`` (ISO string) and ``"duration"`` (int).

    Returns
    -------
    list[dict]
        The subset of *existing_appointments* that overlap.
    """
    conflicts: list[dict[str, Any]] = []
    for appt in existing_appointments:
        appt_start = datetime.fromisoformat(appt["start"])
        appt_duration = int(appt["duration"])
        if check_overlap(proposed_start, proposed_duration, appt_start, appt_duration):
            conflicts.append(appt)
    return conflicts


def format_schedule(
    appointments: list[dict[str, Any]],
    provider_name: str = "",
    date: str = "",
) -> str:
    """Return a human-readable schedule string.

    Parameters
    ----------
    appointments : list[dict]
        Each dict should have ``"start"``, ``"duration"``, ``"patient_name"``,
        and optionally ``"status"``.
    provider_name : str
        Provider name for the header.
    date : str
        Date string for the header.

    Returns
    -------
    str
        A formatted multi-line schedule.
    """
    if not appointments:
        header = f"Schedule for {provider_name} on {date}".strip()
        return f"{header}\n  (no appointments)"

    header = f"Schedule for {provider_name} on {date}".strip()
    lines = [header, "-" * len(header)]

    for appt in sorted(appointments, key=lambda a: a.get("start", "")):
        start_dt = datetime.fromisoformat(appt["start"])
        end_dt = start_dt + timedelta(minutes=int(appt["duration"]))
        patient = appt.get("patient_name", "Unknown")
        status = appt.get("status", "scheduled")
        lines.append(
            f"  {start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}  "
            f"{patient}  [{status}]"
        )

    return "\n".join(lines)


def is_within_hours(
    dt: datetime,
    duration: int,
    hours: dict[str, str],
) -> bool:
    """Check whether an appointment fits within provider working hours.

    Parameters
    ----------
    dt : datetime
        Appointment start.
    duration : int
        Duration in minutes.
    hours : dict
        Must have ``"start"`` and ``"end"`` in ``"HH:MM"`` format.

    Returns
    -------
    bool
    """
    day_start = dt.replace(
        hour=int(hours["start"].split(":")[0]),
        minute=int(hours["start"].split(":")[1]),
        second=0,
        microsecond=0,
    )
    day_end = dt.replace(
        hour=int(hours["end"].split(":")[0]),
        minute=int(hours["end"].split(":")[1]),
        second=0,
        microsecond=0,
    )
    appt_end = dt + timedelta(minutes=duration)
    return dt >= day_start and appt_end <= day_end
