"""Integration tests for GET /runs/metering/current endpoint.

Validates the percent_complete field presence, in-progress vs completed run
behavior, null handling, type enforcement, and backward compatibility
in the current run metering response.
"""

from __future__ import annotations

import pytest

from src.api.runs.metering_current import get_runs_metering_current
from src.models.metering import CurrentMeteringResponse, MeteringData, RunData
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helper — reusable inline run data builders
# ---------------------------------------------------------------------------

def _make_run_data(
    run_id: str = "run-test-001",
    status: str = "in_progress",
    current_index: int = 42,
    total_steps: int = 100,
) -> dict:
    """Build a raw run-data dictionary suitable as input to the handler.

    The handler ``get_runs_metering_current`` expects a flat dictionary with
    ``current_index`` and ``total_steps`` at the top level (or nested inside a
    ``metering`` sub-dictionary).  This helper creates the top-level variant.
    """
    return {
        "id": run_id,
        "status": status,
        "current_index": current_index,
        "total_steps": total_steps,
    }


# ===================================================================
# Phase 2: percent_complete field presence at top level
# ===================================================================


def test_percent_complete_present_in_response() -> None:
    """percent_complete key must exist in the serialised response at the top level.

    AAP validation matrix: "Field missing from response → classified as a bug".
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-presence-001",
            current_index=42,
            total_steps=100,
        )
    )
    data = response.model_dump()
    assert "percent_complete" in data, (
        "percent_complete field must be present in the response — "
        "field missing from response is classified as a bug per AAP"
    )


def test_percent_complete_at_top_level_not_nested() -> None:
    """percent_complete must be a top-level key, not nested inside currentRun.

    The AAP specifies that the ``GET /runs/metering/current`` response places
    ``percent_complete`` alongside ``currentRun`` at the top level.
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-top-level-001",
            current_index=60,
            total_steps=100,
        )
    )
    data = response.model_dump()
    top_level_keys = set(data.keys())
    assert "percent_complete" in top_level_keys, (
        "percent_complete must be a top-level key in the response dict, "
        "not nested inside currentRun"
    )
    # If currentRun is present, the top-level percent_complete is the canonical one
    if data.get("currentRun") is not None:
        assert "percent_complete" in top_level_keys


# ===================================================================
# Phase 3: In-progress run returns value less than 100
# ===================================================================


def test_in_progress_run_percent_less_than_100() -> None:
    """In-progress run (42/100) must produce 0.0 ≤ percent_complete < 100.0.

    AAP validation: "In-progress run → value less than 100".
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-in-progress-001",
            status="in_progress",
            current_index=42,
            total_steps=100,
        )
    )
    assert response.percent_complete is not None
    assert 0.0 <= response.percent_complete < 100.0, (
        f"In-progress run percent_complete ({response.percent_complete}) "
        "must be in [0.0, 100.0)"
    )


def test_in_progress_run_correct_percentage() -> None:
    """current_index=25, total_steps=50 must compute to exactly 50.0%.

    Verifies correct percentage computation through the service layer.
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-exact-calc-001",
            status="in_progress",
            current_index=25,
            total_steps=50,
        )
    )
    assert response.percent_complete == 50.0, (
        f"Expected 50.0 for 25/50 ratio, got {response.percent_complete}"
    )


# ===================================================================
# Phase 4: Completed run returns 100.0
# ===================================================================


def test_completed_run_returns_100() -> None:
    """Completed run (100/100) must have percent_complete == 100.0.

    AAP validation: "Completed run → percent_complete between 0 and 100".
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-completed-001",
            status="completed",
            current_index=100,
            total_steps=100,
        )
    )
    assert response.percent_complete == 100.0, (
        f"Completed run percent_complete must be 100.0, got {response.percent_complete}"
    )


# ===================================================================
# Phase 5: Null value when no active run
# ===================================================================


def test_percent_complete_null_when_no_active_run() -> None:
    """Both percent_complete and currentRun must be None when no data is provided.

    AAP validation: "No data available → null".
    """
    response = get_runs_metering_current(current_run_data=None)
    assert response.percent_complete is None, (
        "percent_complete must be None when current_run_data is None"
    )
    assert response.currentRun is None, (
        "currentRun must be None when current_run_data is None"
    )


def test_percent_complete_null_when_empty_data() -> None:
    """percent_complete must be None when an empty dict is provided.

    An empty dictionary is treated identically to ``None`` — both signify
    "no active run".
    """
    response = get_runs_metering_current(current_run_data={})
    assert response.percent_complete is None, (
        "percent_complete must be None for empty dict input"
    )


def test_percent_complete_present_as_null_not_omitted() -> None:
    """percent_complete key must exist in serialised dict even when value is None.

    The field must never be omitted from the response — it must always be
    present, with a value of ``None`` when no data is available.
    """
    response = get_runs_metering_current(current_run_data=None)
    data = response.model_dump()
    assert "percent_complete" in data, (
        "percent_complete key must be present in response dict, not omitted"
    )
    assert data["percent_complete"] is None, (
        "percent_complete value must be None (not 0, not empty string)"
    )


# ===================================================================
# Phase 6: currentRun object structure
# ===================================================================


def test_current_run_present_when_active() -> None:
    """currentRun must be a RunData instance when valid run data is provided."""
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-active-struct-001",
            status="in_progress",
            current_index=50,
            total_steps=100,
        )
    )
    assert response.currentRun is not None, (
        "currentRun must not be None when valid run data is provided"
    )
    assert isinstance(response.currentRun, RunData), (
        f"currentRun must be a RunData instance, got {type(response.currentRun).__name__}"
    )


def test_current_run_null_when_no_active_run() -> None:
    """currentRun must be None when no run data is provided."""
    response = get_runs_metering_current(current_run_data=None)
    assert response.currentRun is None


def test_current_run_field_name_is_camel_case() -> None:
    """currentRun key must use camelCase in serialised output for backward compatibility.

    The existing ``currentRun`` field uses camelCase to preserve backward
    compatibility with existing API consumers.
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-alias-001",
            current_index=50,
            total_steps=100,
        )
    )
    data = response.model_dump(by_alias=True)
    assert "currentRun" in data, (
        "currentRun field must use camelCase naming for backward compatibility"
    )


# ===================================================================
# Phase 7: Type validation
# ===================================================================


def test_percent_complete_is_float_when_present() -> None:
    """percent_complete must be a float when not None.

    AAP: "must be float or null, never string, boolean, or other type".
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-type-float-001",
            current_index=42,
            total_steps=100,
        )
    )
    assert isinstance(response.percent_complete, float), (
        f"percent_complete must be float, got {type(response.percent_complete).__name__}"
    )


def test_percent_complete_is_none_not_zero_not_string() -> None:
    """When no data is available, percent_complete must be exactly None.

    It must not be ``0``, an empty string, or ``False`` — only ``None``
    represents "no data available".
    """
    response = get_runs_metering_current(current_run_data=None)
    assert response.percent_complete is None
    # Explicit checks that null is not confused with other falsy values
    assert response.percent_complete != 0
    assert response.percent_complete != ""
    assert response.percent_complete is not False


# ===================================================================
# Phase 8: Backward compatibility
# ===================================================================


def test_backward_compatibility_existing_fields_preserved() -> None:
    """Both currentRun and percent_complete must be present — additive change only.

    AAP: "All existing response fields must be preserved exactly as they are".
    """
    response = get_runs_metering_current(
        current_run_data={
            "id": "run-compat-001",
            "status": "in_progress",
            "current_index": 50,
            "total_steps": 100,
            "extra_legacy_field": "should_be_preserved_in_run_data",
        }
    )
    data = response.model_dump()
    assert "currentRun" in data, "currentRun field must be preserved"
    assert "percent_complete" in data, "percent_complete field must be present (additive)"


def test_response_is_current_metering_response_model() -> None:
    """Handler must return a CurrentMeteringResponse instance, not a raw dict."""
    response = get_runs_metering_current(
        current_run_data=_make_run_data(run_id="run-model-type-001")
    )
    assert isinstance(response, CurrentMeteringResponse), (
        f"Handler must return CurrentMeteringResponse, got {type(response).__name__}"
    )


def test_model_validates_fixture_data(mock_current_run_data: dict) -> None:
    """CurrentMeteringResponse.model_validate() must accept conftest fixture data.

    The ``mock_current_run_data`` fixture provides a response-shaped dictionary
    that should be directly parseable by the Pydantic model.
    """
    model = CurrentMeteringResponse.model_validate(mock_current_run_data)
    assert model.percent_complete == 42.0, (
        f"Fixture percent_complete should be 42.0, got {model.percent_complete}"
    )
    assert model.currentRun is not None, (
        "Fixture should produce a non-None currentRun"
    )


def test_model_validates_null_fixture_data(mock_null_metering_data: dict) -> None:
    """CurrentMeteringResponse must accept null-metering fixture data.

    The ``mock_null_metering_data`` fixture provides a dict with
    ``percent_complete=None``.  The model's ``extra="allow"`` config allows
    the ``runs`` key to pass through without error.
    """
    model = CurrentMeteringResponse.model_validate(mock_null_metering_data)
    assert model.percent_complete is None, (
        "Null metering fixture should produce percent_complete=None"
    )


# ===================================================================
# Phase 9: Model validation via Pydantic
# ===================================================================


def test_current_metering_response_rejects_percent_above_100() -> None:
    """Value > 100 must raise ValidationError — classified as a bug per AAP.

    AAP validation matrix: "Value exceeds 100 → Classified as a bug".
    """
    with pytest.raises(ValidationError):
        CurrentMeteringResponse(currentRun=None, percent_complete=100.1)


def test_current_metering_response_rejects_percent_below_zero() -> None:
    """Value < 0 must raise ValidationError — classified as a bug per AAP.

    AAP validation matrix: "Value below 0 → Classified as a bug".
    """
    with pytest.raises(ValidationError):
        CurrentMeteringResponse(currentRun=None, percent_complete=-0.1)


def test_current_metering_response_rejects_string_type() -> None:
    """String type must raise ValidationError — wrong data type is a bug per AAP.

    AAP validation matrix: "Wrong data type (e.g., string) → Classified as a bug".
    """
    with pytest.raises(ValidationError):
        CurrentMeteringResponse(currentRun=None, percent_complete="42")


# ===================================================================
# Phase 10: Consistent field naming
# ===================================================================


def test_field_name_is_percent_complete_snake_case() -> None:
    """Field must be named ``percent_complete`` (snake_case) — per AAP Goal 3.

    AAP: "The field name must be uniform across all three endpoints".
    """
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-naming-001",
            current_index=50,
            total_steps=100,
        )
    )
    data = response.model_dump()
    assert "percent_complete" in data, (
        "Field must use snake_case: percent_complete"
    )
    assert "percentComplete" not in data, (
        "Field must NOT use camelCase: percentComplete — "
        "consistent snake_case naming required per AAP Goal 3"
    )


# ===================================================================
# Additional coverage: JSON serialisation and model_dump_json()
# ===================================================================


def test_model_dump_json_includes_percent_complete() -> None:
    """model_dump_json() must include percent_complete in the JSON string output."""
    response = get_runs_metering_current(
        current_run_data=_make_run_data(
            run_id="run-json-001",
            current_index=75,
            total_steps=100,
        )
    )
    json_str = response.model_dump_json()
    assert '"percent_complete"' in json_str, (
        "percent_complete field must appear in JSON serialised output"
    )


def test_model_dump_json_null_percent_complete() -> None:
    """model_dump_json() must render percent_complete as JSON null, not omit it."""
    response = get_runs_metering_current(current_run_data=None)
    json_str = response.model_dump_json()
    assert '"percent_complete"' in json_str, (
        "percent_complete key must appear in JSON even when value is null"
    )
    assert "null" in json_str, (
        "percent_complete null value must be rendered as JSON null"
    )
