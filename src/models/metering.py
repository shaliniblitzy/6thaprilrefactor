"""Pydantic response models for metering API endpoints with percent_complete field.

This module defines the core Pydantic 2.x models used by the Blitzy Platform's
metering-related API endpoints:

- ``MeteringData``  — inline metering object with ``percent_complete`` and related
  fields, reused both standalone and as a nested object within project responses.
- ``RunData``       — individual run entry containing id, status, and nested metering.
- ``MeteringResponse``       — top-level response for ``GET /runs/metering``.
- ``CurrentMeteringResponse`` — top-level response for ``GET /runs/metering/current``.

All models enforce:
  * ``percent_complete`` typed as ``Optional[float]`` with range ``[0.0, 100.0]``
  * ``default=None`` so the field is always present in serialised output (never omitted)
  * ``ConfigDict(extra="allow")`` for backward compatibility with unknown fields
  * Pydantic 2.x API only (``BaseModel``, ``Field``, ``ConfigDict``)

This is a foundational model file with **no internal project imports** — it may be
freely imported by ``src.models.project``, ``src.api.*``, and test modules without
risk of circular dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Shared type-enforcement helper
# ---------------------------------------------------------------------------

def _reject_non_numeric(value: object) -> object:
    """Pre-validation guard that rejects ``bool`` and ``str`` for *percent_complete*.

    Pydantic 2.x default ("lax") mode silently coerces ``"50"`` → ``50.0``
    and ``True`` → ``1.0``.  The API contract requires *strict* type
    enforcement: only ``int``, ``float``, and ``None`` are permitted.

    This function is used as a ``mode='before'`` field validator on every
    ``percent_complete`` field across all models.
    """
    if value is None:
        return value
    # bool MUST be checked before int/float because bool is a subclass of int
    if isinstance(value, bool):
        raise ValueError(
            "percent_complete must be a numeric value (int or float) or None, "
            f"got {type(value).__name__}"
        )
    if isinstance(value, str):
        raise ValueError(
            "percent_complete must be a numeric value (int or float) or None, "
            f"got {type(value).__name__}"
        )
    if not isinstance(value, (int, float)):
        raise ValueError(
            "percent_complete must be a numeric value (int or float) or None, "
            f"got {type(value).__name__}"
        )
    return value


# ---------------------------------------------------------------------------
# MeteringData — inline / nested metering object
# ---------------------------------------------------------------------------

class MeteringData(BaseModel):
    """Metering data containing percent_complete and related metering fields.

    Used as the inline metering object in both metering API responses and the
    nested metering object within project responses (``ProjectData.metering``).

    Attributes
    ----------
    percent_complete : Optional[float]
        Completion percentage of the code generation run (0.0–100.0 inclusive)
        or ``None`` when no metering data is available.
    estimated_hours_saved : Optional[float]
        Estimated hours saved by the code generation run (>= 0.0) or ``None``.
    estimated_lines_generated : Optional[int]
        Estimated lines of code generated (>= 0) or ``None``.
    """

    model_config = ConfigDict(extra="allow")

    percent_complete: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Completion percentage of the code generation run "
            "(0.0-100.0) or null when not applicable"
        ),
    )
    estimated_hours_saved: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Estimated hours saved by code generation",
    )
    estimated_lines_generated: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated lines of code generated",
    )

    @field_validator("percent_complete", mode="before")
    @classmethod
    def _enforce_percent_type(cls, value: object) -> object:
        """Reject ``bool`` and ``str`` — only numeric or ``None`` allowed."""
        return _reject_non_numeric(value)


# ---------------------------------------------------------------------------
# RunData — individual run entry
# ---------------------------------------------------------------------------

class RunData(BaseModel):
    """Represents a single run entry in the metering response.

    Each run object carries an identifier, a status label, and an optional
    nested ``MeteringData`` block that contains per-run metering metrics
    (including ``percent_complete``).

    Attributes
    ----------
    id : Optional[str]
        Unique run identifier.
    status : Optional[str]
        Current run status (e.g. ``"completed"``, ``"in_progress"``).
    metering : Optional[MeteringData]
        Metering data for this individual run.
    """

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(
        default=None,
        description="Run identifier",
    )
    status: Optional[str] = Field(
        default=None,
        description="Run status",
    )
    metering: Optional[MeteringData] = Field(
        default=None,
        description="Metering data for this run",
    )


# ---------------------------------------------------------------------------
# MeteringResponse — GET /runs/metering top-level response
# ---------------------------------------------------------------------------

class MeteringResponse(BaseModel):
    """Response model for ``GET /runs/metering?projectId=xxx`` endpoint.

    Returns metering data for multiple runs with a **top-level**
    ``percent_complete`` field representing the overall completion percentage
    of the code generation runs.

    Expected JSON shape::

        {
            "runs": [ ... ],
            "percent_complete": 85.5
        }

    Attributes
    ----------
    runs : Optional[List[RunData]]
        List of run objects with their metering data.
    percent_complete : Optional[float]
        Overall completion percentage (0.0–100.0) or ``None`` when not
        applicable.
    """

    model_config = ConfigDict(extra="allow")

    runs: Optional[List[RunData]] = Field(
        default=None,
        description="List of run objects with their metering data",
    )
    percent_complete: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Overall completion percentage of the code generation runs "
            "(0.0-100.0) or null when not applicable"
        ),
    )

    @field_validator("percent_complete", mode="before")
    @classmethod
    def _enforce_percent_type(cls, value: object) -> object:
        """Reject ``bool`` and ``str`` — only numeric or ``None`` allowed."""
        return _reject_non_numeric(value)


# ---------------------------------------------------------------------------
# CurrentMeteringResponse — GET /runs/metering/current top-level response
# ---------------------------------------------------------------------------

class CurrentMeteringResponse(BaseModel):
    """Response model for ``GET /runs/metering/current`` endpoint.

    Returns current run metering data with a **top-level**
    ``percent_complete`` field representing the completion percentage of the
    active code generation run.

    Expected JSON shape::

        {
            "currentRun": { ... },
            "percent_complete": 42.0
        }

    Note
    ----
    The ``currentRun`` field intentionally uses *camelCase* to preserve
    backward compatibility with existing API consumers while the new
    ``percent_complete`` field uses *snake_case* per the AAP naming standard.

    Attributes
    ----------
    currentRun : Optional[RunData]
        Current active run data.
    percent_complete : Optional[float]
        Completion percentage of the current code generation run (0.0–100.0)
        or ``None`` when not applicable.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    currentRun: Optional[RunData] = Field(
        default=None,
        alias="currentRun",
        description="Current active run data",
    )
    percent_complete: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Completion percentage of the current code generation run "
            "(0.0-100.0) or null when not applicable"
        ),
    )

    @field_validator("percent_complete", mode="before")
    @classmethod
    def _enforce_percent_type(cls, value: object) -> object:
        """Reject ``bool`` and ``str`` — only numeric or ``None`` allowed."""
        return _reject_non_numeric(value)
