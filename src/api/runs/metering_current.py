"""Route handler for GET /runs/metering/current endpoint returning current run metering with percent_complete.

This module implements the ``get_runs_metering_current`` handler that powers the
``GET /runs/metering/current`` API endpoint.  The endpoint returns the current
(active) run's metering data with a **top-level** ``percent_complete`` field
representing the completion percentage of the active code generation run.

Typical consumers poll this endpoint for live run status during active code
generation sessions.

Response contract
-----------------
* ``percent_complete`` is ALWAYS present at the **top level** of the response
  (alongside ``currentRun``), typed as ``Optional[float]`` in the range
  ``[0.0, 100.0]`` or ``None`` when no active run or no data exists.
* ``currentRun`` uses *camelCase* to preserve backward compatibility with
  existing API consumers.
* The handler delegates all percent computation to the service layer
  (``src.services.metering_service``) and uses Pydantic models for response
  construction (``src.models.metering``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.models.metering import CurrentMeteringResponse, RunData
from src.services.metering_service import (
    compute_percent_from_metering_data,
    get_percent_complete,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_runs_metering_current(
    current_run_data: Optional[dict] = None,
) -> CurrentMeteringResponse:
    """Handle ``GET /runs/metering/current`` — return current run with percent_complete.

    Processes a raw run-data dictionary, computes the run-completion percentage
    via the service layer, and returns a fully typed
    :class:`~src.models.metering.CurrentMeteringResponse` model with the
    ``percent_complete`` field at the **top level** of the response payload.

    Parameters
    ----------
    current_run_data : Optional[dict]
        Raw current run data dictionary containing run progress state.  May
        include keys such as ``"id"``, ``"status"``, ``"current_index"``,
        ``"total_steps"``, and an optional nested ``"metering"`` dictionary.
        ``None`` or an empty dictionary both signify "no active run".

    Returns
    -------
    CurrentMeteringResponse
        Pydantic response model with:
        * ``currentRun`` — ``RunData`` instance (or ``None`` when inactive)
        * ``percent_complete`` — ``float`` in ``[0.0, 100.0]`` (or ``None``)

    Examples
    --------
    >>> resp = get_runs_metering_current({"id": "run-1", "status": "in_progress",
    ...                                    "current_index": 50, "total_steps": 100})
    >>> resp.percent_complete
    50.0

    >>> resp = get_runs_metering_current(None)
    >>> resp.percent_complete is None
    True
    >>> resp.currentRun is None
    True
    """

    # ------------------------------------------------------------------
    # Step 1 — Handle null / missing / empty data
    # When no run data is available the correct response is a model with
    # both fields set to None — never 0, empty string, or omitted.
    # ------------------------------------------------------------------
    if not current_run_data:
        return CurrentMeteringResponse(
            currentRun=None,
            percent_complete=None,
        )

    # ------------------------------------------------------------------
    # Step 2 — Compute percent_complete via service layer
    # Primary path: use compute_percent_from_metering_data which extracts
    # current_index / total_steps from the dict and delegates internally.
    # ------------------------------------------------------------------
    percent: Optional[float] = compute_percent_from_metering_data(current_run_data)

    # ------------------------------------------------------------------
    # Step 3 — Fallback: check nested metering sub-object
    # If the primary extraction found no progress counters at the top
    # level of the dict, they may reside inside a nested "metering" key.
    # ------------------------------------------------------------------
    if percent is None:
        nested_metering: Any = current_run_data.get("metering")
        if isinstance(nested_metering, dict):
            percent = get_percent_complete(
                current_index=_safe_int(nested_metering.get("current_index")),
                total_steps=_safe_int(nested_metering.get("total_steps")),
            )

    # ------------------------------------------------------------------
    # Step 4 — Build RunData model with enriched metering
    # Ensure the inner metering sub-object carries the freshly computed
    # percent_complete so the serialised output is consistent at every
    # nesting level.
    # ------------------------------------------------------------------
    current_run: RunData = _build_run_data(current_run_data, percent)

    # ------------------------------------------------------------------
    # Step 5 — Build and return the top-level response
    # percent_complete is placed at the TOP LEVEL alongside currentRun.
    # ------------------------------------------------------------------
    return CurrentMeteringResponse(
        currentRun=current_run,
        percent_complete=percent,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_run_data(
    raw_data: Dict[str, Any],
    percent: Optional[float],
) -> RunData:
    """Construct a :class:`RunData` instance with an enriched metering object.

    Creates a shallow copy of *raw_data*, injects the computed
    *percent* into its ``"metering"`` sub-dictionary (creating one if absent),
    and returns a fully populated ``RunData`` model.

    Parameters
    ----------
    raw_data : Dict[str, Any]
        The raw run-data dictionary (must not be ``None`` or empty — the caller
        is responsible for that guard).
    percent : Optional[float]
        The computed ``percent_complete`` value to inject into the metering
        sub-object.

    Returns
    -------
    RunData
        A Pydantic model representing the individual run entry.
    """

    # Shallow copy so we never mutate the caller's dict
    enriched: Dict[str, Any] = dict(raw_data)

    # Enrich or create the metering sub-object with percent_complete
    existing_metering: Any = enriched.get("metering")
    if isinstance(existing_metering, dict):
        enriched["metering"] = {**existing_metering, "percent_complete": percent}
    else:
        enriched["metering"] = {"percent_complete": percent}

    return RunData(**enriched)


def _safe_int(value: Any) -> Optional[int]:
    """Safely coerce a value to ``int``, returning ``None`` on failure.

    Used when extracting ``current_index`` or ``total_steps`` from raw
    dictionaries where the value type is uncertain.  This mirrors the
    ``_safe_int()`` helper in ``src.api.runs.metering`` for consistent
    defensive type coercion across both metering handlers.

    Parameters
    ----------
    value : Any
        The raw value to convert.

    Returns
    -------
    Optional[int]
        The integer representation, or ``None`` if coercion is not possible.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
