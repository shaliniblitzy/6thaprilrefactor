"""
Business logic service for computing the ``percent_complete`` metering field.

This module is the **single source of truth** for calculating the run-completion
percentage across the Blitzy Platform.  All three API endpoints that surface
metering data delegate to the functions defined here:

* ``GET /runs/metering``          → :func:`get_percent_complete`
* ``GET /runs/metering/current``  → :func:`get_percent_complete`
* ``GET /project``                → :func:`compute_percent_from_metering_data`

Design principles
-----------------
* **Pure functions** — no side effects, no external state, no I/O.
* **Centralised validation** — every computed value passes through
  :func:`src.validators.percent_complete.validate_percent_complete` before
  being returned, guaranteeing consistent type and range enforcement.
* **Null semantics** — ``None`` is the only acceptable representation of
  "no data available"; the module never returns ``0``, an empty string, or
  any other sentinel.
* **Clamped range** — raw percentages are clamped to ``[0.0, 100.0]``
  *before* validation so that transient anomalies (e.g. retries pushing
  ``current_index`` past ``total_steps``) do not produce out-of-range values.
"""

from typing import Optional

from src.validators.percent_complete import validate_percent_complete


# ======================================================================
# Public API
# ======================================================================


def get_percent_complete(
    current_index: Optional[int] = None,
    total_steps: Optional[int] = None,
) -> Optional[float]:
    """Compute the run-completion percentage from step counters.

    Converts a ``current_index / total_steps`` ratio into a floating-point
    percentage in the range ``[0.0, 100.0]``.  The result is clamped to that
    range and then passed through the centralised
    :func:`~src.validators.percent_complete.validate_percent_complete`
    validator for final type and range enforcement.

    Parameters
    ----------
    current_index : Optional[int]
        The current step index of the code-generation run.  ``None`` when no
        progress data is available.
    total_steps : Optional[int]
        The total number of steps in the run.  ``None`` when run metadata is
        incomplete or unavailable.

    Returns
    -------
    Optional[float]
        A validated percentage (``0.0`` – ``100.0`` inclusive) or ``None``
        when progress cannot be determined.

    Examples
    --------
    >>> get_percent_complete(50, 100)
    50.0
    >>> get_percent_complete(100, 100)
    100.0
    >>> get_percent_complete(None, 100) is None
    True
    >>> get_percent_complete(150, 100)   # clamped to 100.0
    100.0
    """

    # ------------------------------------------------------------------
    # Step 1 — Null / missing-data handling
    # When either counter is absent the percentage is indeterminate.
    # Returning None (not 0 or -1) signals "no data" per the API contract.
    # ------------------------------------------------------------------
    if current_index is None or total_steps is None:
        return None

    # ------------------------------------------------------------------
    # Step 2 — Guard against invalid total_steps
    # A non-positive denominator makes the ratio meaningless and would
    # cause a ZeroDivisionError or a nonsensical negative result.
    # ------------------------------------------------------------------
    if total_steps <= 0:
        return None

    # ------------------------------------------------------------------
    # Step 3 — Compute the raw percentage
    # Simple ratio converted to a 0-100 scale.
    # ------------------------------------------------------------------
    raw_percent: float = (current_index / total_steps) * 100.0

    # ------------------------------------------------------------------
    # Step 4 — Clamp to the valid range [0.0, 100.0]
    # Handles anomalies such as current_index > total_steps (retries) or
    # negative current_index values without surfacing invalid numbers to
    # API consumers.  Clamping happens BEFORE validation so the validator
    # never encounters out-of-range values from this code path.
    # ------------------------------------------------------------------
    clamped: float = max(0.0, min(100.0, raw_percent))

    # ------------------------------------------------------------------
    # Step 5 — Centralised validation
    # Delegates to the shared validator to guarantee consistent type and
    # range checks across the entire codebase.
    # ------------------------------------------------------------------
    return validate_percent_complete(clamped)


def compute_percent_from_metering_data(
    metering_data: Optional[dict] = None,
) -> Optional[float]:
    """Extract and compute ``percent_complete`` from a metering dictionary.

    This convenience wrapper accepts the raw metering dictionary that API
    handlers typically receive, pulls out the ``current_index`` and
    ``total_steps`` keys, and delegates to :func:`get_percent_complete`.

    Parameters
    ----------
    metering_data : Optional[dict]
        A dictionary that *may* contain ``"current_index"`` and
        ``"total_steps"`` keys.  ``None`` or an empty dictionary both
        result in a ``None`` return value.

    Returns
    -------
    Optional[float]
        A validated percentage (``0.0`` – ``100.0`` inclusive) or ``None``
        when the input is missing, empty, or lacks the required keys.

    Examples
    --------
    >>> compute_percent_from_metering_data({"current_index": 50, "total_steps": 100})
    50.0
    >>> compute_percent_from_metering_data(None) is None
    True
    >>> compute_percent_from_metering_data({}) is None
    True
    """

    # ------------------------------------------------------------------
    # Step 1 — Handle None or empty input
    # Both represent the absence of metering data; the correct response
    # is None, not an error.
    # ------------------------------------------------------------------
    if not metering_data:
        return None

    # ------------------------------------------------------------------
    # Step 2 — Safely extract progress counters
    # Using dict.get() with a None default avoids KeyError and naturally
    # flows into get_percent_complete's own None-handling logic.
    # ------------------------------------------------------------------
    current_index: Optional[int] = metering_data.get("current_index")
    total_steps: Optional[int] = metering_data.get("total_steps")

    # ------------------------------------------------------------------
    # Step 3 — Delegate to the primary computation function
    # All clamping, validation, and null-handling rules are applied by
    # get_percent_complete — no need to duplicate them here.
    # ------------------------------------------------------------------
    return get_percent_complete(current_index, total_steps)
