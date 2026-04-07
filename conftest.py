"""Pytest configuration and shared test fixtures for the Blitzy Platform API tests.

This module provides:
- **Shared fixtures** for mocking API response data across all three metering
  endpoints (``GET /runs/metering``, ``GET /runs/metering/current``,
  ``GET /project``).
- **Test data factory functions** (``make_metering_response``,
  ``make_project_response``) for building response payloads with custom
  ``percent_complete`` values.
- **Edge-case / boundary fixtures** (``boundary_values``) covering the full
  validation matrix from the AAP (Section 0.7.2).

All fixtures consistently use ``percent_complete`` (snake_case) as the field
name, matching the Pydantic model definitions in ``src.models.metering`` and
``src.models.project``.

Fixture scoping strategy:
- Mutable dict fixtures use **function** scope (default) so that tests cannot
  accidentally mutate shared state.
- The ``boundary_values`` fixture uses **session** scope because its data is
  a list of immutable tuples that is never mutated in-place.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from src.models.metering import MeteringResponse
from src.models.project import ProjectResponse


# ---------------------------------------------------------------------------
# Test Data Factories
# ---------------------------------------------------------------------------


def make_metering_response(
    percent_complete: Optional[float] = None,
    runs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a dictionary matching the ``GET /runs/metering`` response schema.

    The returned dictionary can be fed directly into
    :pyclass:`MeteringResponse.model_validate` for Pydantic validation, or
    used as raw mock data in tests that inspect plain dicts.

    Parameters
    ----------
    percent_complete : Optional[float]
        Overall completion percentage (0.0–100.0) or ``None`` when not
        applicable.  Defaults to ``None``.
    runs : Optional[List[Dict[str, Any]]]
        A list of run-data dictionaries.  Each entry should conform to the
        ``RunData`` schema (``id``, ``status``, ``metering``).  Defaults to
        an empty list when ``None`` is passed.

    Returns
    -------
    Dict[str, Any]
        A dictionary with ``"runs"`` and ``"percent_complete"`` keys that
        mirrors the JSON structure of the ``GET /runs/metering`` endpoint.

    Examples
    --------
    >>> payload = make_metering_response(percent_complete=85.0)
    >>> payload["percent_complete"]
    85.0
    >>> payload["runs"]
    []
    >>> validated = MeteringResponse.model_validate(payload)
    >>> validated.percent_complete
    85.0
    """
    if runs is None:
        runs = []
    return {
        "runs": runs,
        "percent_complete": percent_complete,
    }


def make_project_response(
    percent_complete: Optional[float] = None,
    project_id: Optional[str] = "project-default-001",
    project_name: Optional[str] = "Default Test Project",
) -> Dict[str, Any]:
    """Build a dictionary matching the ``GET /project`` response schema.

    The returned dictionary nests the ``percent_complete`` value inside
    ``project.metering.percent_complete``, matching the structural
    characteristic of the project endpoint.

    Parameters
    ----------
    percent_complete : Optional[float]
        Completion percentage (0.0–100.0) or ``None``.  Defaults to ``None``.
    project_id : Optional[str]
        Project identifier string.  Defaults to ``"project-default-001"``.
    project_name : Optional[str]
        Human-readable project name.  Defaults to ``"Default Test Project"``.

    Returns
    -------
    Dict[str, Any]
        A dictionary with a ``"project"`` key whose value contains ``"id"``,
        ``"name"``, and ``"metering"`` (with ``"percent_complete"``).

    Examples
    --------
    >>> payload = make_project_response(percent_complete=100.0)
    >>> payload["project"]["metering"]["percent_complete"]
    100.0
    >>> validated = ProjectResponse.model_validate(payload)
    >>> validated.project.metering.percent_complete
    100.0
    """
    return {
        "project": {
            "id": project_id,
            "name": project_name,
            "metering": {
                "percent_complete": percent_complete,
            },
        },
    }


# ---------------------------------------------------------------------------
# Shared Fixtures — Metering API Response Data
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_metering_data() -> Dict[str, Any]:
    """Sample ``GET /runs/metering`` response with a valid ``percent_complete``.

    Provides a realistic metering response containing two run objects (one
    completed and one in-progress) with an overall ``percent_complete`` of
    75.5, suitable for tests that need representative multi-run data.

    Returns
    -------
    Dict[str, Any]
        ``{"runs": [...], "percent_complete": 75.5}``
    """
    return {
        "runs": [
            {
                "id": "run-001",
                "status": "completed",
                "metering": {
                    "percent_complete": 100.0,
                    "estimated_hours_saved": 3.2,
                    "estimated_lines_generated": 850,
                },
            },
            {
                "id": "run-002",
                "status": "in_progress",
                "metering": {
                    "percent_complete": 51.0,
                    "estimated_hours_saved": 1.5,
                    "estimated_lines_generated": 400,
                },
            },
        ],
        "percent_complete": 75.5,
    }


@pytest.fixture
def mock_current_run_data() -> Dict[str, Any]:
    """Sample ``GET /runs/metering/current`` response for an in-progress run.

    Provides a current-run response with ``percent_complete`` set to 42.0,
    representing an active code generation run that is not yet finished.

    Returns
    -------
    Dict[str, Any]
        ``{"currentRun": {...}, "percent_complete": 42.0}``
    """
    return {
        "currentRun": {
            "id": "run-active-001",
            "status": "in_progress",
            "metering": {
                "percent_complete": 42.0,
                "estimated_hours_saved": 2.1,
                "estimated_lines_generated": 500,
            },
        },
        "percent_complete": 42.0,
    }


@pytest.fixture
def mock_project_data() -> Dict[str, Any]:
    """Sample ``GET /project`` response with completed-run metering.

    Provides a project response where the nested metering block has
    ``percent_complete`` set to 100.0 — the completed-run scenario.

    Returns
    -------
    Dict[str, Any]
        ``{"project": {"id": ..., "name": ..., "metering": {"percent_complete": 100.0, ...}}}``
    """
    return {
        "project": {
            "id": "project-456",
            "name": "Blitzy Code Gen Project",
            "metering": {
                "percent_complete": 100.0,
                "estimated_hours_saved": 8.5,
                "estimated_lines_generated": 2400,
            },
        },
    }


@pytest.fixture
def mock_null_metering_data() -> Dict[str, Any]:
    """Metering response where ``percent_complete`` is ``None`` (no data).

    Represents the "no data available" scenario: no runs have been executed
    and the metering percentage is explicitly null.

    Returns
    -------
    Dict[str, Any]
        ``{"runs": [], "percent_complete": None}``
    """
    return {
        "runs": [],
        "percent_complete": None,
    }


# ---------------------------------------------------------------------------
# Edge-Case / Boundary Data Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def boundary_values() -> List[tuple]:
    """Boundary test data for ``percent_complete`` validation.

    Returns a list of ``(value, is_valid)`` tuples covering the complete
    validation matrix from AAP Section 0.7.2:

    - **Valid values**: 0.0 (min), 100.0 (max), 50.5 (mid-range), ``None``
    - **Invalid values**: -0.1 (below range), 100.1 (above range), ``"50"``
      (string type), ``True`` (boolean type)

    Tests should iterate over these tuples and assert that valid values are
    accepted by the Pydantic models and that invalid values are rejected with
    a ``ValidationError``.

    Returns
    -------
    List[tuple]
        Each tuple is ``(test_value, expected_validity_bool)``.
    """
    return [
        (0.0, True),        # minimum valid value
        (100.0, True),      # maximum valid value
        (50.5, True),       # mid-range valid value
        (None, True),       # null is valid
        (50, True),         # integer accepted as float (int→float coercion)
        (-0.1, False),      # below range — invalid
        (100.1, False),     # above range — invalid
        ("50", False),      # string type — invalid
        (True, False),      # boolean type — invalid
    ]
