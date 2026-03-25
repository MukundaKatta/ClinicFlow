"""Configuration for ClinicFlow."""

from __future__ import annotations

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings loaded from environment or defaults."""

    db_path: str = Field(
        default_factory=lambda: os.getenv("CLINICFLOW_DB_PATH", ":memory:"),
        description="Path to the SQLite database file.",
    )
    default_duration: int = Field(
        default_factory=lambda: int(os.getenv("CLINICFLOW_DEFAULT_DURATION", "30")),
        description="Default appointment duration in minutes.",
    )
    slot_interval: int = Field(
        default_factory=lambda: int(os.getenv("CLINICFLOW_SLOT_INTERVAL", "15")),
        description="Slot interval in minutes for availability search.",
    )
    log_level: str = Field(
        default_factory=lambda: os.getenv("CLINICFLOW_LOG_LEVEL", "INFO"),
        description="Logging level.",
    )


def get_settings() -> Settings:
    """Return a Settings instance populated from the environment."""
    return Settings()
