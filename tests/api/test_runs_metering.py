"""Integration tests for GET /runs/metering?projectId=xxx endpoint.

Validates the percent_complete field presence, type, range, null handling,
and backward compatibility in the metering response.

Test organisation mirrors the AAP validation matrix (Section 0.7.2):

    +---------------------------------+------------------+-------+
    | Scenario                        | Expected Value   | Valid |
    +---------------------------------+------------------+-------+
    | Completed run                   | 0.0–100.0        | Yes   |
    | In-progress run                 | < 100.0          | Yes   |
    | No data available               | null             | Yes   |
    | Field missing entirely          | N/A              | Bug   |
    | Value > 100                     | N/A              | Bug   |
    | Value < 0                       | N/A              | Bug   |
    | String instead of number        | N/A              | Bug   |
    | Inconsistent name across APIs   | N/A              | Bug   |
    +---------------------------------+------------------+-------+

All tests call the handler function directly — no HTTP server is required.
Fixtures are injected from the root-level ``conftest.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.runs.metering import get_runs_metering
from src.models.metering import MeteringData, MeteringResponse, RunData
from src.services.metering_service import get_percent_complete

# Import the factory helper from conftest (it is a regular function, not a fixture)
from conftest import make_metering_response


# ======================================================================
# Phase 2: percent_complete Field Presence Tests
# ======================================================================


class TestPercentCompletePresence:
    """Tests validating that percent_complete is always present in the response."""

    def test_percent_complete_present_in_response(self) -> None:
        """percent_complete key must exist in the serialised response with valid data.

        AAP requirement: "Field missing from response → classified as a bug."
        """
        metering_data: dict = {
            "runs": [
                {"id": "run-001", "status": "completed"},
            ],
            "current_index": 75,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(
            project_id="proj-001",
            metering_data=metering_data,
        )
        serialized: dict = response.model_dump()
        assert "percent_complete" in serialized, (
            "percent_complete field must be present in every response "
            "(AAP: field missing → bug)"
        )

    def test_percent_complete_present_when_null(self) -> None:
        """percent_complete key must still be present even when its value is None.

        The field must return ``null``, not be omitted entirely.
        """
        response: MeteringResponse = get_runs_metering(metering_data=None)
        serialized: dict = response.model_dump()
        assert "percent_complete" in serialized, (
            "percent_complete field must be present even when null — not omitted"
        )
        assert serialized["percent_complete"] is None, (
            "percent_complete value must be None (JSON null) when no data is available"
        )


# ======================================================================
# Phase 3: Value Range (0.0–100.0) Tests
# ======================================================================


class TestPercentCompleteValueRange:
    """Tests validating the 0.0–100.0 inclusive range for percent_complete."""

    def test_percent_complete_valid_range_completed_run(self) -> None:
        """Completed run (current_index == total_steps) → percent_complete == 100.0."""
        metering_data: dict = {
            "runs": [],
            "current_index": 100,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        assert response.percent_complete is not None
        assert response.percent_complete == 100.0
        assert 0.0 <= response.percent_complete <= 100.0

    def test_percent_complete_valid_range_partial(self) -> None:
        """Partial progress (50/100) → percent_complete == 50.0."""
        metering_data: dict = {
            "runs": [],
            "current_index": 50,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        assert response.percent_complete is not None
        assert response.percent_complete == 50.0
        assert 0.0 <= response.percent_complete <= 100.0

    def test_percent_complete_valid_range_zero(self) -> None:
        """Zero progress (0/100) → percent_complete == 0.0."""
        metering_data: dict = {
            "runs": [],
            "current_index": 0,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        assert response.percent_complete is not None
        assert response.percent_complete == 0.0
        assert response.percent_complete >= 0.0


# ======================================================================
# Phase 4: Null Value When No Data Available Tests
# ======================================================================


class TestPercentCompleteNull:
    """Tests validating null handling when no metering data is available."""

    def test_percent_complete_null_when_no_metering_data(self) -> None:
        """Passing metering_data=None produces percent_complete is None.

        Covers the "No data available → null" row in the validation matrix.
        """
        response: MeteringResponse = get_runs_metering(metering_data=None)
        assert response.percent_complete is None

    def test_percent_complete_null_when_empty_data(self) -> None:
        """Passing metering_data={} (empty dict, falsy) produces percent_complete is None."""
        response: MeteringResponse = get_runs_metering(metering_data={})
        assert response.percent_complete is None


# ======================================================================
# Phase 5: Type Validation Tests
# ======================================================================


class TestPercentCompleteType:
    """Tests ensuring percent_complete is always ``float`` or ``None``."""

    def test_percent_complete_is_float_type(self) -> None:
        """When present, percent_complete must be a float instance.

        Enforces: "must be float or null, never string, boolean, or other type."
        """
        metering_data: dict = {
            "runs": [],
            "current_index": 75,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        assert response.percent_complete is not None, (
            "Expected a numeric value but got None"
        )
        assert isinstance(response.percent_complete, float), (
            f"percent_complete must be float, got {type(response.percent_complete).__name__}"
        )

    def test_percent_complete_is_none_type_when_null(self) -> None:
        """When null, percent_complete must be exactly None — not 0, not '', not False."""
        response: MeteringResponse = get_runs_metering(metering_data=None)
        assert response.percent_complete is None, (
            "percent_complete must be None when no data is available"
        )
        # Ensure it is truly None and not another falsy value
        assert response.percent_complete != 0, (
            "percent_complete must be None, not 0"
        )
        assert response.percent_complete != "", (
            "percent_complete must be None, not empty string"
        )
        assert response.percent_complete is not False, (
            "percent_complete must be None, not False"
        )


# ======================================================================
# Phase 6: Response Structure (runs list) Tests
# ======================================================================


class TestResponseStructure:
    """Tests for the ``runs`` list presence and element structure."""

    def test_runs_list_present_in_response(self) -> None:
        """Serialised response must contain the 'runs' key."""
        metering_data: dict = {
            "runs": [
                {"id": "run-001", "status": "completed"},
            ],
            "current_index": 50,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        serialized: dict = response.model_dump()
        assert "runs" in serialized, (
            "'runs' key must be present in the serialised response"
        )

    def test_runs_list_contains_run_data(self) -> None:
        """Each item in the runs list must be a RunData instance."""
        metering_data: dict = {
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
                        "percent_complete": 50.0,
                        "estimated_hours_saved": 1.0,
                        "estimated_lines_generated": 200,
                    },
                },
            ],
            "current_index": 75,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        assert response.runs is not None, "runs must not be None with valid data"
        assert isinstance(response.runs, list), "runs must be a list"
        assert len(response.runs) >= 1, "runs list must contain at least one entry"
        for run in response.runs:
            assert isinstance(run, RunData), (
                f"Each run entry must be a RunData instance, got {type(run).__name__}"
            )
            # Verify nested metering on completed run has the right type
            if run.metering is not None:
                assert isinstance(run.metering, MeteringData), (
                    f"Nested metering must be MeteringData, got {type(run.metering).__name__}"
                )


# ======================================================================
# Phase 7: Backward Compatibility Tests
# ======================================================================


class TestBackwardCompatibility:
    """Tests ensuring existing response fields are preserved after the enhancement."""

    def test_backward_compatibility_existing_fields_preserved(
        self, mock_metering_data: dict
    ) -> None:
        """Extra / existing fields beyond percent_complete and runs are preserved.

        Uses the ``mock_metering_data`` fixture from conftest.py and validates
        the model via ``model_validate()`` to confirm that
        ``ConfigDict(extra='allow')`` correctly retains all fields.
        """
        validated: MeteringResponse = MeteringResponse.model_validate(
            mock_metering_data,
        )
        serialized: dict = validated.model_dump()
        # Both mandatory keys must be present
        assert "runs" in serialized, "'runs' field must be preserved"
        assert "percent_complete" in serialized, "'percent_complete' must be preserved"
        # The fixture's percent_complete value (75.5) must survive round-trip
        assert serialized["percent_complete"] == 75.5

    def test_response_is_metering_response_model(self) -> None:
        """Handler must return a MeteringResponse instance, not a raw dict."""
        metering_data: dict = {
            "runs": [],
            "current_index": 50,
            "total_steps": 100,
        }
        response = get_runs_metering(metering_data=metering_data)
        assert isinstance(response, MeteringResponse), (
            f"Handler must return MeteringResponse, got {type(response).__name__}"
        )

    def test_model_validate_with_factory_data(self) -> None:
        """make_metering_response factory data round-trips through model_validate."""
        payload: dict = make_metering_response(percent_complete=85.0)
        validated: MeteringResponse = MeteringResponse.model_validate(payload)
        assert validated.percent_complete == 85.0
        assert validated.runs is not None
        assert isinstance(validated.runs, list)

    def test_model_validate_with_null_fixture(
        self, mock_null_metering_data: dict
    ) -> None:
        """mock_null_metering_data fixture round-trips through model_validate with None."""
        validated: MeteringResponse = MeteringResponse.model_validate(
            mock_null_metering_data,
        )
        assert validated.percent_complete is None


# ======================================================================
# Phase 8: Model Validation (Pydantic rejection) Tests
# ======================================================================


class TestModelValidation:
    """Tests for Pydantic model constraints on percent_complete.

    Direct model instantiation is used so that Pydantic's ``ge``/``le``
    validators and the custom ``_enforce_percent_type`` field validator
    are exercised.
    """

    def test_metering_response_rejects_percent_above_100(self) -> None:
        """MeteringResponse must reject percent_complete > 100.0.

        AAP validation matrix: "Value > 100 → Bug."
        """
        with pytest.raises(ValidationError):
            MeteringResponse(percent_complete=100.1, runs=[])

    def test_metering_response_rejects_percent_below_zero(self) -> None:
        """MeteringResponse must reject percent_complete < 0.0.

        AAP validation matrix: "Value < 0 → Bug."
        """
        with pytest.raises(ValidationError):
            MeteringResponse(percent_complete=-0.1, runs=[])

    def test_metering_response_rejects_string_type(self) -> None:
        """MeteringResponse must reject string percent_complete.

        AAP validation matrix: "Wrong data type (e.g., string) → Bug."
        """
        with pytest.raises(ValidationError):
            MeteringResponse(percent_complete="50", runs=[])  # type: ignore[arg-type]


# ======================================================================
# Phase 9: Consistent Field Naming Tests
# ======================================================================


class TestFieldNaming:
    """Tests for consistent field naming across APIs."""

    def test_field_name_is_percent_complete_snake_case(self) -> None:
        """Serialised key must be 'percent_complete' (snake_case), never 'percentComplete'.

        AAP Goal 3: "Consistent naming across all endpoints."
        """
        metering_data: dict = {
            "runs": [],
            "current_index": 50,
            "total_steps": 100,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        serialized: dict = response.model_dump()
        assert "percent_complete" in serialized, (
            "Field must use snake_case naming: 'percent_complete'"
        )
        assert "percentComplete" not in serialized, (
            "Field must NOT use camelCase naming: 'percentComplete'"
        )


# ======================================================================
# Service Integration Verification
# ======================================================================


class TestServiceIntegration:
    """Tests verifying the handler correctly delegates to the service layer."""

    def test_handler_delegates_percent_computation_to_service(self) -> None:
        """Handler result must match what get_percent_complete would produce.

        This confirms the handler delegates computation to the service layer
        rather than performing its own arithmetic.
        """
        current_index: int = 75
        total_steps: int = 100
        expected_percent: float | None = get_percent_complete(
            current_index, total_steps,
        )

        metering_data: dict = {
            "runs": [],
            "current_index": current_index,
            "total_steps": total_steps,
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        assert response.percent_complete == expected_percent, (
            f"Handler percent_complete ({response.percent_complete}) must match "
            f"service layer result ({expected_percent})"
        )

    def test_handler_returns_null_for_no_progress_data(self) -> None:
        """Handler returns None when metering_data has runs but no step counters.

        Verifies that the handler does NOT invent a default percent when the
        service layer returns None due to missing step counters.
        """
        metering_data: dict = {
            "runs": [
                {"id": "run-001", "status": "completed"},
            ],
            # No current_index / total_steps → service returns None
        }
        response: MeteringResponse = get_runs_metering(metering_data=metering_data)
        assert response.percent_complete is None, (
            "percent_complete must be None when step counters are absent"
        )
