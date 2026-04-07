"""Pydantic response models for the GET /project endpoint.

This module defines the Pydantic 2.x response models used by the Blitzy
Platform's ``GET /project?id=xxx`` API endpoint.  The endpoint returns a
project object with embedded metering data, including the
``percent_complete`` field that tracks code generation run progress.

Models
------
- ``ProjectData``     — inner project object containing ``id``, ``name``,
  and a nested ``MeteringData`` block with ``percent_complete``.
- ``ProjectResponse`` — top-level envelope wrapping ``ProjectData`` under
  the ``project`` key.

Design Decisions
----------------
* ``MeteringData`` is **imported** from ``src.models.metering`` (not
  redefined) to ensure the ``percent_complete`` field has identical
  validation semantics (``Optional[float]``, ``ge=0.0``, ``le=100.0``,
  strict type enforcement) across every API endpoint.
* Both models use ``ConfigDict(extra="allow")`` so that additional fields
  returned by the API (or sent by consumers) are preserved, maintaining
  full backward compatibility with existing integrations.
* All explicitly modelled fields default to ``None`` — serialisation
  therefore always includes them in the JSON output, guaranteeing
  ``percent_complete`` is **never silently omitted**.

Expected JSON shapes::

    # With metering data
    {
        "project": {
            "id": "project-123",
            "name": "My Project",
            "metering": {
                "percent_complete": 100.0,
                "estimated_hours_saved": 5.2,
                "estimated_lines_generated": 1200
            }
        }
    }

    # Without metering data
    {
        "project": {
            "id": "project-123",
            "name": "My Project",
            "metering": null
        }
    }

    # Metering present but no progress yet
    {
        "project": {
            "id": "project-123",
            "name": "My Project",
            "metering": {
                "percent_complete": null
            }
        }
    }
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.metering import MeteringData


# ---------------------------------------------------------------------------
# ProjectData — inner project object
# ---------------------------------------------------------------------------


class ProjectData(BaseModel):
    """Represents the project data returned by the ``GET /project`` endpoint.

    The ``metering`` field embeds a :class:`MeteringData` instance that
    carries the ``percent_complete`` progress indicator alongside other
    metering metrics (``estimated_hours_saved``,
    ``estimated_lines_generated``).

    Attributes
    ----------
    id : Optional[str]
        Unique project identifier (e.g. ``"project-123"``).
    name : Optional[str]
        Human-readable project name.
    metering : Optional[MeteringData]
        Inline metering data for the project's code generation runs.
        Contains ``percent_complete`` (0.0–100.0 or ``None``),
        ``estimated_hours_saved``, and ``estimated_lines_generated``.
        ``None`` when no metering data is available for the project.
    """

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(
        default=None,
        description="Project identifier",
    )
    name: Optional[str] = Field(
        default=None,
        description="Project name",
    )
    metering: Optional[MeteringData] = Field(
        default=None,
        description=(
            "Inline metering data including percent_complete, "
            "estimated_hours_saved, and estimated_lines_generated"
        ),
    )


# ---------------------------------------------------------------------------
# ProjectResponse — top-level API response envelope
# ---------------------------------------------------------------------------


class ProjectResponse(BaseModel):
    """Response model for ``GET /project?id=xxx`` endpoint.

    Wraps the :class:`ProjectData` object under the ``project`` key.
    The ``percent_complete`` field is **not** at the top level — it is
    nested inside ``project.metering.percent_complete``, which is the
    distinguishing structural characteristic of this endpoint compared
    to ``/runs/metering`` and ``/runs/metering/current``.

    Example
    -------
    >>> data = ProjectResponse.model_validate({
    ...     "project": {
    ...         "id": "proj-1",
    ...         "name": "Demo",
    ...         "metering": {"percent_complete": 75.0}
    ...     }
    ... })
    >>> data.project.metering.percent_complete
    75.0

    Attributes
    ----------
    project : Optional[ProjectData]
        Project data with embedded metering.  ``None`` when no project
        data is available.
    """

    model_config = ConfigDict(extra="allow")

    project: Optional[ProjectData] = Field(
        default=None,
        description="Project data with embedded metering",
    )
