"""Route handler for GET /runs/metering endpoint returning metering data with percent_complete.

This module implements the ``get_runs_metering`` handler function that services
the ``GET /runs/metering?projectId=xxx`` API endpoint.  The handler:

1. Accepts an optional project identifier and raw metering data dictionary.
2. Parses individual run entries from the metering payload into typed
   :class:`~src.models.metering.RunData` objects.
3. Delegates overall ``percent_complete`` computation to the service layer
   (:func:`~src.services.metering_service.compute_percent_from_metering_data`
   and :func:`~src.services.metering_service.get_percent_complete`).
4. Returns a :class:`~src.models.metering.MeteringResponse` Pydantic model
   whose serialised form always contains the top-level ``percent_complete``
   field (as ``float`` in ``[0.0, 100.0]`` or ``null``).

Key design rules (derived from the Agent Action Plan):

* ``percent_complete`` uses **snake_case** — never camelCase.
* ``percent_complete`` is at the **top level** of the response alongside
  ``runs`` — never nested inside individual run objects.
* The field is **always present** in every response — omission is a defect.
* ``None`` / ``null`` is the only valid representation of "no data".
* All percentage computation is **delegated** to the service layer; the
  handler never performs arithmetic on step counters directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.models.metering import MeteringResponse, RunData
from src.services.metering_service import (
    compute_percent_from_metering_data,
    get_percent_complete,
)


# ======================================================================
# Public API
# ======================================================================


def get_runs_metering(
    project_id: Optional[str] = None,
    metering_data: Optional[dict] = None,
) -> MeteringResponse:
    """Handle ``GET /runs/metering?projectId=xxx`` requests.

    Returns metering data for multiple runs of a code-generation project with
    the ``percent_complete`` field at the **top level** of the response.

    Parameters
    ----------
    project_id : Optional[str]
        The project identifier extracted from the ``?projectId=xxx`` query
        parameter.  Used to identify which project's runs to retrieve
        metering data for.  When ``None``, no project-specific filtering
        is applied — the raw *metering_data* is used as-is.
    metering_data : Optional[dict]
        Raw metering data dictionary that may contain:

        * ``"runs"`` — a list of dicts, each with ``id``, ``status``, and
          an optional nested ``"metering"`` sub-dict.
        * ``"current_index"`` — current step index for overall progress.
        * ``"total_steps"`` — total steps for overall progress computation.

        When ``None`` or empty, the handler returns ``null`` for all fields.

    Returns
    -------
    MeteringResponse
        A Pydantic model that serialises to::

            {
                "runs": [ ... ],
                "percent_complete": 85.5
            }

        or, when no data is available::

            {
                "runs": null,
                "percent_complete": null
            }

    Notes
    -----
    * ``percent_complete`` is always at the **top level** — never nested
      inside individual run objects.
    * Computation is delegated to the service layer; this handler does not
      perform any percentage arithmetic itself.
    * The field uses ``snake_case`` naming per AAP Goal 3.
    * The field is **always present** in the serialised output (never omitted).
    """

    # ------------------------------------------------------------------
    # Step 1 — Handle null / missing metering data
    # Per the API contract, ``None`` or empty metering_data means
    # "no data available" — return null for all fields (not 0, not empty
    # string, not an empty list).
    # ------------------------------------------------------------------
    if not metering_data:
        return MeteringResponse(runs=None, percent_complete=None)

    # ------------------------------------------------------------------
    # Step 2 — Extract and build typed run entries
    # Parse the "runs" key from the metering payload.  Each entry is
    # converted into a RunData Pydantic model for type-safe access.
    # ------------------------------------------------------------------
    raw_runs: Any = metering_data.get("runs")
    runs_list: Optional[List[RunData]] = _build_runs_list(raw_runs)

    # ------------------------------------------------------------------
    # Step 3 — Compute top-level percent_complete via the service layer
    # The primary path uses compute_percent_from_metering_data which
    # extracts current_index / total_steps from the dict.  If the dict
    # carries these keys at the top level the computation succeeds.
    # ------------------------------------------------------------------
    percent: Optional[float] = compute_percent_from_metering_data(
        metering_data,
    )

    # ------------------------------------------------------------------
    # Step 3b — Fallback: explicit current_index / total_steps extraction
    # If compute_percent_from_metering_data returned None (e.g. neither
    # key was present at the top level) but explicit step counters are
    # available under different nesting, attempt a direct call to
    # get_percent_complete as a secondary resolution path.
    # ------------------------------------------------------------------
    if percent is None:
        current_index: Optional[int] = _safe_int(
            metering_data.get("current_index"),
        )
        total_steps: Optional[int] = _safe_int(
            metering_data.get("total_steps"),
        )
        if current_index is not None and total_steps is not None:
            percent = get_percent_complete(current_index, total_steps)

    # ------------------------------------------------------------------
    # Step 4 — Build the response model
    # Both "runs" and "percent_complete" are set explicitly so neither
    # is ever omitted from the serialised output.
    # ------------------------------------------------------------------
    response = MeteringResponse(
        runs=runs_list,
        percent_complete=percent,
    )

    # ------------------------------------------------------------------
    # Step 5 — Validate serialised response integrity
    # Field-presence is mandatory per the AAP validation matrix.  This
    # guard ensures that model serialisation never silently drops either
    # required key.
    # ------------------------------------------------------------------
    _validate_response_integrity(response)

    return response


# ======================================================================
# Private helpers
# ======================================================================


def _build_runs_list(
    raw_runs: Any,
) -> Optional[List[RunData]]:
    """Parse a raw runs collection into a list of typed ``RunData`` objects.

    Parameters
    ----------
    raw_runs : Any
        The value extracted from ``metering_data["runs"]``.  Expected to be
        a ``list`` of dicts or ``RunData`` instances.  ``None`` or non-list
        values produce a ``None`` return.

    Returns
    -------
    Optional[List[RunData]]
        A list of validated ``RunData`` models, or ``None`` when no usable
        run data is available.
    """
    if raw_runs is None:
        return None

    if not isinstance(raw_runs, list):
        return None

    typed_runs: List[RunData] = []
    for entry in raw_runs:
        run: Optional[RunData] = _parse_run_entry(entry)
        if run is not None:
            typed_runs.append(run)

    # Return None (not empty list) when no valid entries were found,
    # preserving null semantics for the "no data" case.
    return typed_runs if typed_runs else None


def _parse_run_entry(entry: Any) -> Optional[RunData]:
    """Convert a single raw run entry into a validated ``RunData`` instance.

    If the entry is a dictionary, it is unpacked into a ``RunData`` Pydantic
    model.  If any sub-metering data includes ``current_index`` and
    ``total_steps`` but lacks a ``percent_complete``, the value is computed
    via :func:`get_percent_complete` and injected before model construction.

    Parameters
    ----------
    entry : Any
        A dictionary with run fields or an existing ``RunData`` instance.

    Returns
    -------
    Optional[RunData]
        A validated run data model, or ``None`` if the entry is unusable.
    """
    # Already a RunData instance — return directly after verifying fields
    if isinstance(entry, RunData):
        # Access core fields to confirm model integrity
        _verify_run_fields(entry)
        return entry

    if not isinstance(entry, dict):
        return None

    try:
        # Enrich nested metering with computed percent_complete when absent
        enriched: Dict[str, Any] = _enrich_run_metering(entry)
        run = RunData(**enriched)
        # Verify core field accessibility on the constructed model
        _verify_run_fields(run)
        return run
    except (ValueError, TypeError):
        # Pydantic validation failure — skip this malformed entry
        return None


def _enrich_run_metering(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Compute ``percent_complete`` for a run's nested metering when missing.

    If the run's ``metering`` sub-dict contains ``current_index`` and
    ``total_steps`` but no ``percent_complete``, the percentage is computed
    via the service layer and inserted into a shallow copy of the metering
    dict.

    Parameters
    ----------
    entry : Dict[str, Any]
        A raw run dictionary that may contain a ``"metering"`` sub-dict.

    Returns
    -------
    Dict[str, Any]
        The (potentially enriched) run dictionary.  The original dict is
        never mutated; a shallow copy is returned when enrichment occurs.
    """
    run_metering: Any = entry.get("metering")

    if not isinstance(run_metering, dict):
        return entry

    # Only compute if percent_complete is absent from the nested metering
    if run_metering.get("percent_complete") is not None:
        return entry

    current_index: Optional[int] = _safe_int(
        run_metering.get("current_index"),
    )
    total_steps: Optional[int] = _safe_int(
        run_metering.get("total_steps"),
    )

    if current_index is not None and total_steps is not None:
        computed: Optional[float] = get_percent_complete(
            current_index, total_steps,
        )
        enriched_metering: Dict[str, Any] = {
            **run_metering,
            "percent_complete": computed,
        }
        return {**entry, "metering": enriched_metering}

    return entry


def _verify_run_fields(run: RunData) -> None:
    """Access core ``RunData`` fields to verify model integrity.

    This helper reads each expected attribute on a ``RunData`` instance,
    ensuring that the Pydantic model was constructed correctly and all
    fields are accessible at runtime.

    Parameters
    ----------
    run : RunData
        The run data model to verify.
    """
    # Access each documented field — will raise AttributeError if the
    # model definition changes unexpectedly.
    _ = run.id
    _ = run.status
    _ = run.metering


def _validate_response_integrity(response: MeteringResponse) -> None:
    """Verify that the serialised response contains all mandatory fields.

    The AAP validation matrix mandates that ``percent_complete`` and
    ``runs`` are always present in every response.  A missing field is
    classified as a bug.  This function uses ``model_dump()`` to obtain
    the serialised form and checks for key presence.

    Parameters
    ----------
    response : MeteringResponse
        The constructed response model to validate.

    Raises
    ------
    ValueError
        If a mandatory field (``percent_complete`` or ``runs``) is missing
        from the serialised payload.
    """
    serialized: Dict[str, Any] = response.model_dump()

    if "percent_complete" not in serialized:
        raise ValueError(
            "Response integrity violation: 'percent_complete' field is "
            "missing from the serialized MeteringResponse. This field "
            "must always be present per the API contract."
        )

    if "runs" not in serialized:
        raise ValueError(
            "Response integrity violation: 'runs' field is missing from "
            "the serialized MeteringResponse. This field must always be "
            "present per the API contract."
        )


def _safe_int(value: Any) -> Optional[int]:
    """Safely coerce a value to ``int``, returning ``None`` on failure.

    Used when extracting ``current_index`` or ``total_steps`` from raw
    dictionaries where the value type is uncertain.

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
