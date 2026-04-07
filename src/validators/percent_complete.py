"""
Centralized validation module for the percent_complete field.

This module provides the ``validate_percent_complete()`` function used across all
three Blitzy Platform API endpoints (``GET /runs/metering``,
``GET /runs/metering/current``, ``GET /project``) to enforce consistent type
checking, range constraints (0.0–100.0), and null handling for the
percent_complete metering field.

The validator is intentionally a pure Python utility function with no external
dependencies (no Pydantic, no logging, no side effects).  Pydantic-level field
validation lives in the models layer; this module provides the shared business
rule that those models and the service layer both delegate to.
"""

from typing import Optional


def validate_percent_complete(value: object) -> Optional[float]:
    """Validate and normalise a *percent_complete* value.

    Ensures the value is either ``None`` (no metering data available) or a
    numeric value (``int`` or ``float``) within the inclusive range
    ``[0.0, 100.0]``.  Boolean values are explicitly rejected despite
    ``bool`` being a subclass of ``int`` in Python.

    Parameters
    ----------
    value : object
        The raw value to validate.  Accepts any type so the function can
        perform exhaustive type checking on untrusted input.  Valid inputs
        are ``None``, ``int``, or ``float`` within ``[0.0, 100.0]``.

    Returns
    -------
    Optional[float]
        The validated value cast to ``float`` (range 0.0–100.0 inclusive),
        or ``None`` when no metering data is available.

    Raises
    ------
    TypeError
        If *value* is not ``None``, ``int``, or ``float``.  This includes
        ``bool``, ``str``, ``list``, ``dict``, and every other non-numeric
        type.
    ValueError
        If the numeric value falls outside the valid range ``[0.0, 100.0]``.

    Examples
    --------
    >>> validate_percent_complete(None)   # no data available

    >>> validate_percent_complete(50.5)   # valid float
    50.5
    >>> validate_percent_complete(50)     # integer → float
    50.0
    >>> validate_percent_complete(0.0)    # lower boundary
    0.0
    >>> validate_percent_complete(100.0)  # upper boundary
    100.0
    """

    # ------------------------------------------------------------------
    # Step 1 — Null handling
    # None is a perfectly valid state that indicates "no metering data is
    # available" for the current run or project.
    # ------------------------------------------------------------------
    if value is None:
        return None

    # ------------------------------------------------------------------
    # Step 2 — Type enforcement
    # CRITICAL: ``bool`` must be checked BEFORE ``int``/``float`` because
    # in Python ``bool`` is a subclass of ``int``
    # (i.e. ``isinstance(True, int)`` evaluates to ``True``).
    # ------------------------------------------------------------------
    if isinstance(value, bool):
        raise TypeError(
            "percent_complete must be a numeric value (int or float) or None, "
            f"got {type(value).__name__}"
        )

    if not isinstance(value, (int, float)):
        raise TypeError(
            "percent_complete must be a numeric value (int or float) or None, "
            f"got {type(value).__name__}"
        )

    # ------------------------------------------------------------------
    # Step 3 — Convert to float
    # Guarantees a consistent return type regardless of whether the caller
    # passed an ``int`` or a ``float``.
    # ------------------------------------------------------------------
    result: float = float(value)

    # ------------------------------------------------------------------
    # Step 4 — Range validation
    # The percent_complete field must satisfy 0.0 ≤ value ≤ 100.0.
    # Out-of-range values are considered bugs per the API contract.
    # ------------------------------------------------------------------
    if result < 0.0:
        raise ValueError(
            f"percent_complete must be between 0.0 and 100.0, got {result}"
        )

    if result > 100.0:
        raise ValueError(
            f"percent_complete must be between 0.0 and 100.0, got {result}"
        )

    # ------------------------------------------------------------------
    # Step 5 — Return the validated float
    # ------------------------------------------------------------------
    return result
