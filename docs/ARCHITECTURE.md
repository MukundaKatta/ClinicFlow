# ClinicFlow Architecture

## Overview

ClinicFlow is a Python library for managing clinic appointments. It provides intelligent scheduling with conflict detection, availability management, and statistics — all backed by SQLite for lightweight, zero-configuration persistence.

## System Design

```
┌─────────────────────────────────────────────┐
│              Client Application             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│            ClinicFlow (core.py)              │
│                                             │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ │
│  │ Provider  │ │  Patient  │ │Appointment │ │
│  │ Manager   │ │  Manager  │ │ Scheduler  │ │
│  └──────────┘ └───────────┘ └─────┬──────┘ │
│                                   │        │
│         ┌─────────────────────────┤        │
│         │                         │        │
│  ┌──────▼──────┐  ┌──────────────▼──────┐  │
│  │  Conflict   │  │   Availability      │  │
│  │  Detector   │  │   Manager           │  │
│  │ (utils.py)  │  │   (utils.py)        │  │
│  └─────────────┘  └────────────────────-┘  │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           SQLite Database                   │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │providers │ │ patients │ │appointments │ │
│  └──────────┘ └──────────┘ └─────────────┘ │
└─────────────────────────────────────────────┘
```

## Module Breakdown

### `core.py` — ClinicFlow Class

The central orchestrator. Manages all CRUD operations and coordinates between sub-components.

| Method | Purpose |
|--------|---------|
| `add_provider()` | Register a healthcare provider with specialty and hours |
| `add_patient()` | Register a patient with contact info |
| `schedule_appointment()` | Create an appointment with validation |
| `cancel_appointment()` | Mark an appointment as cancelled |
| `find_available_slots()` | Query open slots for a provider on a date |
| `detect_conflicts()` | Check for overlapping appointments |
| `get_schedule()` | Retrieve a provider's daily schedule |
| `get_stats()` | Aggregate clinic-wide statistics |

### `utils.py` — Utility Functions

Pure functions for time-slot arithmetic and formatting:

- **`generate_time_slots()`** — Produces a list of time windows within a range
- **`check_overlap()`** — Boolean overlap test for two time ranges
- **`detect_conflicts()`** — Filters a list of appointments for overlaps
- **`format_schedule()`** — Renders appointments as a readable string
- **`is_within_hours()`** — Validates an appointment fits within provider hours

### `config.py` — Settings

Pydantic-based configuration loaded from environment variables with sensible defaults.

## Data Model

### `providers`

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| name | TEXT | Provider full name |
| specialty | TEXT | Medical specialty |
| hours | TEXT (JSON) | Working hours `{"start": "HH:MM", "end": "HH:MM"}` |
| created_at | TEXT | ISO timestamp |

### `patients`

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| name | TEXT | Patient full name |
| info | TEXT (JSON) | Contact and metadata |
| created_at | TEXT | ISO timestamp |

### `appointments`

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| patient_id | TEXT (FK) | References `patients.id` |
| provider_id | TEXT (FK) | References `providers.id` |
| start | TEXT | ISO datetime of appointment start |
| duration | INTEGER | Duration in minutes |
| status | TEXT | `scheduled` or `cancelled` |
| created_at | TEXT | ISO timestamp |

## Design Decisions

1. **SQLite** — Zero-dependency persistence; ideal for single-process clinics and educational use.
2. **Pydantic for config** — Validation and type safety for settings.
3. **UUID primary keys** — Avoids auto-increment collisions in distributed scenarios.
4. **Pure utility functions** — `utils.py` functions are stateless and independently testable.
5. **Context manager support** — `ClinicFlow` supports `with` blocks for safe resource cleanup.
