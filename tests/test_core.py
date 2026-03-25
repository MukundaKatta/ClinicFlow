"""Tests for the ClinicFlow scheduler engine."""

from datetime import datetime

import pytest

from clinicflow import ClinicFlow


@pytest.fixture()
def clinic() -> ClinicFlow:
    """Return a ClinicFlow instance backed by an in-memory database."""
    return ClinicFlow(db_path=":memory:")


@pytest.fixture()
def seeded_clinic(clinic: ClinicFlow) -> tuple[ClinicFlow, str, str]:
    """Return a clinic with one provider and one patient already added."""
    provider_id = clinic.add_provider(
        name="Dr. Smith",
        specialty="General Practice",
        hours={"start": "09:00", "end": "17:00"},
    )
    patient_id = clinic.add_patient(
        name="Jane Doe",
        info={"phone": "555-0123"},
    )
    return clinic, provider_id, patient_id


class TestAddProviderAndPatient:
    """Verify provider and patient registration."""

    def test_add_provider(self, clinic: ClinicFlow) -> None:
        pid = clinic.add_provider("Dr. Lee", "Cardiology", {"start": "08:00", "end": "16:00"})
        assert isinstance(pid, str)
        assert len(pid) == 36  # UUID length

    def test_add_patient(self, clinic: ClinicFlow) -> None:
        pid = clinic.add_patient("John Doe", {"email": "john@example.com"})
        assert isinstance(pid, str)
        assert len(pid) == 36


class TestScheduling:
    """Verify appointment scheduling, conflict detection, and cancellation."""

    def test_schedule_and_retrieve(
        self, seeded_clinic: tuple[ClinicFlow, str, str]
    ) -> None:
        clinic, provider_id, patient_id = seeded_clinic
        appt = clinic.schedule_appointment(
            patient_id=patient_id,
            provider_id=provider_id,
            dt=datetime(2026, 4, 1, 10, 0),
            duration=30,
        )
        assert appt["status"] == "scheduled"
        assert appt["duration"] == 30

        schedule = clinic.get_schedule(provider_id, "2026-04-01")
        assert isinstance(schedule, list)
        assert len(schedule) == 1

    def test_conflict_detection(
        self, seeded_clinic: tuple[ClinicFlow, str, str]
    ) -> None:
        clinic, provider_id, patient_id = seeded_clinic
        clinic.schedule_appointment(
            patient_id=patient_id,
            provider_id=provider_id,
            dt=datetime(2026, 4, 1, 10, 0),
            duration=30,
        )
        # Overlapping appointment should raise
        with pytest.raises(ValueError, match="conflict"):
            clinic.schedule_appointment(
                patient_id=patient_id,
                provider_id=provider_id,
                dt=datetime(2026, 4, 1, 10, 15),
                duration=30,
            )

    def test_cancel_appointment(
        self, seeded_clinic: tuple[ClinicFlow, str, str]
    ) -> None:
        clinic, provider_id, patient_id = seeded_clinic
        appt = clinic.schedule_appointment(
            patient_id=patient_id,
            provider_id=provider_id,
            dt=datetime(2026, 4, 1, 14, 0),
            duration=30,
        )
        result = clinic.cancel_appointment(appt["id"])
        assert result["status"] == "cancelled"

    def test_outside_working_hours_rejected(
        self, seeded_clinic: tuple[ClinicFlow, str, str]
    ) -> None:
        clinic, provider_id, patient_id = seeded_clinic
        with pytest.raises(ValueError, match="outside provider working hours"):
            clinic.schedule_appointment(
                patient_id=patient_id,
                provider_id=provider_id,
                dt=datetime(2026, 4, 1, 7, 0),
                duration=30,
            )


class TestAvailability:
    """Verify available-slot queries."""

    def test_find_available_slots(
        self, seeded_clinic: tuple[ClinicFlow, str, str]
    ) -> None:
        clinic, provider_id, patient_id = seeded_clinic
        # Book one slot
        clinic.schedule_appointment(
            patient_id=patient_id,
            provider_id=provider_id,
            dt=datetime(2026, 4, 1, 10, 0),
            duration=30,
        )
        slots = clinic.find_available_slots(provider_id, "2026-04-01", duration=30)
        # The 10:00 and 10:15 slots should be gone
        start_times = [s["start"] for s in slots]
        assert "10:00" not in start_times
        assert "10:15" not in start_times
        # But 09:00 should still be there
        assert "09:00" in start_times


class TestStats:
    """Verify aggregate statistics."""

    def test_stats(self, seeded_clinic: tuple[ClinicFlow, str, str]) -> None:
        clinic, provider_id, patient_id = seeded_clinic
        appt = clinic.schedule_appointment(
            patient_id=patient_id,
            provider_id=provider_id,
            dt=datetime(2026, 4, 1, 11, 0),
            duration=30,
        )
        clinic.cancel_appointment(appt["id"])

        stats = clinic.get_stats()
        assert stats["total_providers"] == 1
        assert stats["total_patients"] == 1
        assert stats["total_appointments"] == 1
        assert stats["cancelled"] == 1
        assert stats["scheduled"] == 0
