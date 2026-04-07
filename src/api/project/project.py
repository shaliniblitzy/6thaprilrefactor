"""API route handler for GET /project?id=xxx endpoint.

Returns project data with embedded metering information including
the percent_complete field tracking code generation progress.

This is the ONLY endpoint where ``percent_complete`` is **nested** within
``project.metering`` rather than appearing at the top level of the response.
The other two metering endpoints (``GET /runs/metering`` and
``GET /runs/metering/current``) surface the field at the top level.

Usage
-----
>>> from src.api.project.project import get_project
>>> response = get_project(project_id="proj-1", project_data={
...     "id": "proj-1",
...     "name": "Demo",
...     "metering": {"current_index": 50, "total_steps": 100},
... })
>>> response.project.metering.percent_complete
50.0

Design decisions
----------------
* **Service delegation** — all ``percent_complete`` computation is delegated
  to ``src.services.metering_service`` so that calculation, clamping, and
  validation rules remain centralised across the three API endpoints.
* **Model usage** — the response is always a ``ProjectResponse`` wrapping a
  ``ProjectData`` with a nested ``MeteringData`` object, ensuring consistent
  Pydantic-validated serialisation.
* **Null semantics** — when metering data is absent or incomplete, the field
  is explicitly ``None`` (never omitted, never zero, never empty string).
* **Backward compatibility** — all extra fields present in the raw
  ``project_data`` dictionary are preserved because every model uses
  ``ConfigDict(extra="allow")``.
"""

from typing import Any, Dict, Optional

from src.models.metering import MeteringData
from src.models.project import ProjectData, ProjectResponse
from src.services.metering_service import compute_percent_from_metering_data
from src.validators.percent_complete import validate_percent_complete


def get_project(
    project_id: Optional[str] = None,
    project_data: Optional[Dict[str, Any]] = None,
) -> ProjectResponse:
    """Handle ``GET /project?id=xxx`` and return project data with metering.

    Constructs a :class:`ProjectResponse` containing a :class:`ProjectData`
    object with an embedded :class:`MeteringData` block.  The metering block
    always includes the ``percent_complete`` field (``float`` or ``None``),
    satisfying the AAP requirement that the field is **never silently
    omitted** from the response.

    Parameters
    ----------
    project_id : Optional[str]
        The project identifier from the ``id`` query parameter.  When
        ``None`` and ``project_data`` is also ``None``, the handler returns
        a minimal response with all nullable fields set to ``None``.
    project_data : Optional[Dict[str, Any]]
        Pre-fetched raw project data dictionary.  Expected to contain keys
        such as ``"id"``, ``"name"``, and ``"metering"`` (a sub-dict with
        optional ``"current_index"`` / ``"total_steps"`` keys).  When
        ``None``, the handler falls back to using only ``project_id``.

    Returns
    -------
    ProjectResponse
        A Pydantic model with the structure::

            {
                "project": {
                    "id": "...",
                    "name": "...",
                    "metering": {
                        "percent_complete": <float | null>,
                        "estimated_hours_saved": <float | null>,
                        "estimated_lines_generated": <int | null>
                    }
                }
            }

    Examples
    --------
    >>> # Full project data with metering
    >>> resp = get_project(project_data={
    ...     "id": "proj-42",
    ...     "name": "My App",
    ...     "metering": {"current_index": 75, "total_steps": 100},
    ... })
    >>> resp.project.metering.percent_complete
    75.0

    >>> # No project data at all
    >>> resp = get_project()
    >>> resp.project.metering.percent_complete is None
    True

    >>> # Project data without metering sub-dict
    >>> resp = get_project(project_data={"id": "proj-99", "name": "Empty"})
    >>> resp.project.metering.percent_complete is None
    True
    """

    # ------------------------------------------------------------------
    # Step 1 — Handle absent project data
    # When no raw data is provided, return a minimal response.  The
    # percent_complete field MUST still be present (as None) per the AAP
    # requirement: "Field presence is mandatory."
    # ------------------------------------------------------------------
    if project_data is None:
        metering = MeteringData(percent_complete=None)
        project = ProjectData(
            id=project_id,
            name=None,
            metering=metering,
        )
        return ProjectResponse(project=project)

    # ------------------------------------------------------------------
    # Step 2 — Extract raw metering sub-dict from project data
    # The metering dictionary may contain "current_index" and
    # "total_steps" keys used to compute percent_complete.  It may also
    # carry pre-computed metering metrics (estimated_hours_saved,
    # estimated_lines_generated) that must be preserved.
    # ------------------------------------------------------------------
    metering_raw: Dict[str, Any] = project_data.get("metering", {}) or {}

    # ------------------------------------------------------------------
    # Step 3 — Compute percent_complete via the service layer
    # Delegating to compute_percent_from_metering_data centralises the
    # calculation, clamping ([0.0, 100.0]), and validation logic.
    # If metering_raw already has a pre-computed "percent_complete" key,
    # we prefer computing from raw progress counters for consistency.
    # Falls back to the pre-computed value when counters are absent.
    # ------------------------------------------------------------------
    has_progress_counters: bool = (
        "current_index" in metering_raw and "total_steps" in metering_raw
    )

    if has_progress_counters:
        # Compute from raw step counters (most authoritative source)
        percent_complete: Optional[float] = compute_percent_from_metering_data(
            metering_raw
        )
    elif "percent_complete" in metering_raw:
        # Use the pre-computed value and run it through the centralised
        # validator to ensure it respects the [0.0, 100.0] constraint and
        # strict type enforcement (booleans and strings are rejected).
        raw_pct = metering_raw.get("percent_complete")
        if raw_pct is None:
            percent_complete = None
        else:
            try:
                # validate_percent_complete handles type enforcement
                # (rejects bool, str, etc.), range checking, and
                # int→float coercion in a single call — no need for
                # the identity round-trip through get_percent_complete().
                percent_complete = validate_percent_complete(raw_pct)
            except (TypeError, ValueError):
                percent_complete = None
    else:
        # No progress data of any kind — return null
        percent_complete = None

    # ------------------------------------------------------------------
    # Step 4 — Extract other metering fields for the MeteringData object
    # These are preserved from the raw data when available.
    # ------------------------------------------------------------------
    estimated_hours_saved: Optional[float] = metering_raw.get(
        "estimated_hours_saved"
    )
    estimated_lines_generated: Optional[int] = metering_raw.get(
        "estimated_lines_generated"
    )

    # Build the MeteringData model instance.  Extra fields in metering_raw
    # beyond the explicitly modelled ones are passed through via
    # ConfigDict(extra="allow") to preserve backward compatibility.
    extra_metering_fields: Dict[str, Any] = {
        k: v
        for k, v in metering_raw.items()
        if k not in {
            "percent_complete",
            "estimated_hours_saved",
            "estimated_lines_generated",
            "current_index",
            "total_steps",
        }
    }

    metering = MeteringData(
        percent_complete=percent_complete,
        estimated_hours_saved=estimated_hours_saved,
        estimated_lines_generated=estimated_lines_generated,
        **extra_metering_fields,
    )

    # ------------------------------------------------------------------
    # Step 5 — Build the ProjectData instance
    # Extract the project-level fields (id, name) from raw data.
    # The project_id parameter acts as a fallback when the raw data
    # does not include an "id" key.
    # ------------------------------------------------------------------
    resolved_id: Optional[str] = project_data.get("id") or project_id
    resolved_name: Optional[str] = project_data.get("name")

    # Preserve extra project-level fields beyond id, name, metering
    extra_project_fields: Dict[str, Any] = {
        k: v
        for k, v in project_data.items()
        if k not in {"id", "name", "metering"}
    }

    project = ProjectData(
        id=resolved_id,
        name=resolved_name,
        metering=metering,
        **extra_project_fields,
    )

    # ------------------------------------------------------------------
    # Step 6 — Return the top-level ProjectResponse
    # ------------------------------------------------------------------
    return ProjectResponse(project=project)
