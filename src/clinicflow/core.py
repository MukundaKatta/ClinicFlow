"""Core ClinicFlow scheduler engine.

Provides the main ``ClinicFlow`` class that manages providers, patients,
and appointments backed by a SQLite database.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any

from clinicflow.config import Settings, get_settings
from clinicflow.utils import (
    check_overlap,
    detect_conflicts,
    format_schedule,
    generate_time_slots,
    is_within_hours,
)

logger = logging.getLogger(__name__)


class ClinicFlow:
    """Patient appointment scheduler with conflict detection.

    Parameters
    ----------
    db_path : str | None
        Path to the SQLite database.  Defaults to the value in
        :class:`~clinicflow.config.Settings`.
    settings : Settings | None
        Optional pre-built settings object.
    """

    def __init__(
        self,
        db_path: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._db_path = db_path or self._settings.db_path
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        logger.info("ClinicFlow initialised (db=%s)", self._db_path)

    # ------------------------------------------------------------------
    # Database bootstrap
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables if they do not already exist."""
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS providers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                hours TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                info TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                start TEXT NOT NULL,
                duration INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'scheduled',
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (provider_id) REFERENCES providers(id)
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def add_provider(
        self,
        name: str,
        specialty: str,
        hours: dict[str, str],
    ) -> str:
        """Register a new healthcare provider.

        Parameters
        ----------
        name : str
            Full name of the provider.
        specialty : str
            Medical specialty (e.g. ``"Cardiology"``).
        hours : dict[str, str]
            Working hours with ``"start"`` and ``"end"`` keys in ``"HH:MM"``
            format.

        Returns
        -------
        str
            The generated provider ID.
        """
        provider_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO providers (id, name, specialty, hours, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (provider_id, name, specialty, json.dumps(hours), datetime.utcnow().isoformat()),
        )
        self._conn.commit()
        logger.info("Added provider %s (%s)", name, provider_id)
        return provider_id

    def _get_provider(self, provider_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM providers WHERE id = ?", (provider_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Provider not found: {provider_id}")
        return {**dict(row), "hours": json.loads(row["hours"])}

    # ------------------------------------------------------------------
    # Patients
    # ------------------------------------------------------------------

    def add_patient(self, name: str, info: dict[str, Any] | None = None) -> str:
        """Register a new patient.

        Parameters
        ----------
        name : str
            Patient full name.
        info : dict | None
            Arbitrary contact / medical metadata.

        Returns
        -------
        str
            The generated patient ID.
        """
        patient_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO patients (id, name, info, created_at) VALUES (?, ?, ?, ?)",
            (patient_id, name, json.dumps(info or {}), datetime.utcnow().isoformat()),
        )
        self._conn.commit()
        logger.info("Added patient %s (%s)", name, patient_id)
        return patient_id

    # ------------------------------------------------------------------
    # Appointments
    # ------------------------------------------------------------------

    def schedule_appointment(
        self,
        patient_id: str,
        provider_id: str,
        dt: datetime,
        duration: int | None = None,
    ) -> dict[str, Any]:
        """Schedule a new appointment.

        Validates working hours and checks for conflicts before inserting.

        Parameters
        ----------
        patient_id : str
            Existing patient ID.
        provider_id : str
            Existing provider ID.
        dt : datetime
            Desired start time.
        duration : int | None
            Duration in minutes; defaults to
            :pyattr:`Settings.default_duration`.

        Returns
        -------
        dict
            The created appointment record.

        Raises
        ------
        ValueError
            If the slot is outside working hours or conflicts exist.
        """
        duration = duration or self._settings.default_duration
        provider = self._get_provider(provider_id)

        # Validate working hours
        if not is_within_hours(dt, duration, provider["hours"]):
            raise ValueError(
                f"Appointment at {dt} is outside provider working hours "
                f"({provider['hours']['start']}–{provider['hours']['end']})."
            )

        # Conflict check
        conflicts = self.detect_conflicts(provider_id, dt, duration)
        if conflicts:
            raise ValueError(
                f"Scheduling conflict: {len(conflicts)} overlapping "
                f"appointment(s) found for provider {provider_id}."
            )

        appt_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        self._conn.execute(
            "INSERT INTO appointments "
            "(id, patient_id, provider_id, start, duration, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'scheduled', ?)",
            (appt_id, patient_id, provider_id, dt.isoformat(), duration, now),
        )
        self._conn.commit()
        logger.info("Scheduled appointment %s for patient %s", appt_id, patient_id)

        return {
            "id": appt_id,
            "patient_id": patient_id,
            "provider_id": provider_id,
            "start": dt.isoformat(),
            "duration": duration,
            "status": "scheduled",
        }

    def cancel_appointment(self, appointment_id: str) -> dict[str, Any]:
        """Cancel an existing appointment.

        Parameters
        ----------
        appointment_id : str
            The appointment to cancel.

        Returns
        -------
        dict
            Updated appointment record with ``status='cancelled'``.

        Raises
        ------
        ValueError
            If the appointment is not found.
        """
        row = self._conn.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Appointment not found: {appointment_id}")

        self._conn.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            (appointment_id,),
        )
        self._conn.commit()
        logger.info("Cancelled appointment %s", appointment_id)
        return {**dict(row), "status": "cancelled"}

    # ------------------------------------------------------------------
    # Availability & conflicts
    # ------------------------------------------------------------------

    def find_available_slots(
        self,
        provider_id: str,
        date: str,
        duration: int | None = None,
        interval: int | None = None,
    ) -> list[dict[str, str]]:
        """Return open time slots for a provider on a given date.

        Parameters
        ----------
        provider_id : str
            Provider to query.
        date : str
            Date in ``"YYYY-MM-DD"`` format.
        duration : int | None
            Slot length in minutes; defaults to ``default_duration``.
        interval : int | None
            Step size in minutes; defaults to ``slot_interval``.

        Returns
        -------
        list[dict[str, str]]
            Available slots with ``"date"``, ``"start"``, and ``"end"`` keys.
        """
        duration = duration or self._settings.default_duration
        interval = interval or self._settings.slot_interval
        provider = self._get_provider(provider_id)

        all_slots = generate_time_slots(
            provider["hours"]["start"],
            provider["hours"]["end"],
            interval,
            date,
        )

        # Fetch booked appointments for this provider on the given date
        rows = self._conn.execute(
            "SELECT start, duration FROM appointments "
            "WHERE provider_id = ? AND status = 'scheduled' AND start LIKE ?",
            (provider_id, f"{date}%"),
        ).fetchall()
        booked = [{"start": r["start"], "duration": r["duration"]} for r in rows]

        available: list[dict[str, str]] = []
        for slot in all_slots:
            slot_dt = datetime.strptime(f"{date} {slot['start']}", "%Y-%m-%d %H:%M")
            conflicts = detect_conflicts(slot_dt, duration, booked)
            if not conflicts:
                available.append(slot)

        return available

    def detect_conflicts(
        self,
        provider_id: str,
        dt: datetime,
        duration: int,
    ) -> list[dict[str, Any]]:
        """Check for scheduling conflicts for a provider.

        Parameters
        ----------
        provider_id : str
            Provider to check.
        dt : datetime
            Proposed start time.
        duration : int
            Proposed duration in minutes.

        Returns
        -------
        list[dict]
            Any existing appointments that overlap with the proposed slot.
        """
        date_str = dt.strftime("%Y-%m-%d")
        rows = self._conn.execute(
            "SELECT * FROM appointments "
            "WHERE provider_id = ? AND status = 'scheduled' AND start LIKE ?",
            (provider_id, f"{date_str}%"),
        ).fetchall()

        existing = [dict(r) for r in rows]
        return detect_conflicts(dt, duration, existing)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_schedule(
        self,
        provider_id: str,
        date: str,
        formatted: bool = False,
    ) -> list[dict[str, Any]] | str:
        """Return a provider's schedule for a given date.

        Parameters
        ----------
        provider_id : str
            Provider to query.
        date : str
            Date in ``"YYYY-MM-DD"`` format.
        formatted : bool
            If ``True``, return a human-readable string instead of raw dicts.

        Returns
        -------
        list[dict] | str
        """
        provider = self._get_provider(provider_id)
        rows = self._conn.execute(
            "SELECT a.*, p.name AS patient_name FROM appointments a "
            "JOIN patients p ON a.patient_id = p.id "
            "WHERE a.provider_id = ? AND a.status = 'scheduled' AND a.start LIKE ? "
            "ORDER BY a.start",
            (provider_id, f"{date}%"),
        ).fetchall()

        appointments = [dict(r) for r in rows]

        if formatted:
            return format_schedule(appointments, provider["name"], date)
        return appointments

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about the clinic.

        Returns
        -------
        dict
            Keys: ``total_providers``, ``total_patients``,
            ``total_appointments``, ``scheduled``, ``cancelled``.
        """
        cur = self._conn.cursor()
        providers = cur.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        patients = cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        total = cur.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        scheduled = cur.execute(
            "SELECT COUNT(*) FROM appointments WHERE status = 'scheduled'"
        ).fetchone()[0]
        cancelled = cur.execute(
            "SELECT COUNT(*) FROM appointments WHERE status = 'cancelled'"
        ).fetchone()[0]

        return {
            "total_providers": providers,
            "total_patients": patients,
            "total_appointments": total,
            "scheduled": scheduled,
            "cancelled": cancelled,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        logger.info("ClinicFlow connection closed.")

    def __enter__(self) -> "ClinicFlow":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
