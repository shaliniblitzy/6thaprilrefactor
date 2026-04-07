"""Pydantic response models for Blitzy Platform API endpoints with percent_complete field.

This package re-exports the core Pydantic 2.x model classes used by the
Blitzy Platform's API endpoints for metering and project data.  Consumers
can import directly from ``src.models`` as a convenience shortcut:

    from src.models import MeteringResponse, ProjectResponse

Submodule access is also preserved — the following still works:

    from src.models.metering import MeteringData

Re-exported classes
-------------------
From ``src.models.metering``:
    - ``MeteringData``             — inline metering object (percent_complete, estimated_hours_saved, estimated_lines_generated)
    - ``RunData``                  — individual run entry (id, status, nested MeteringData)
    - ``MeteringResponse``         — top-level response for GET /runs/metering
    - ``CurrentMeteringResponse``  — top-level response for GET /runs/metering/current

From ``src.models.project``:
    - ``ProjectData``              — inner project object (id, name, nested MeteringData)
    - ``ProjectResponse``          — top-level response for GET /project
"""

from src.models.metering import (
    CurrentMeteringResponse,
    MeteringData,
    MeteringResponse,
    RunData,
)
from src.models.project import ProjectData, ProjectResponse

__all__ = [
    "MeteringData",
    "MeteringResponse",
    "CurrentMeteringResponse",
    "RunData",
    "ProjectResponse",
    "ProjectData",
]
