"""Comprehensive tests for Pydantic metering and project response models with percent_complete field.

This test module validates the data model layer independently of API handlers,
ensuring that Pydantic enforces type, range, null, serialization, and
backward-compatibility constraints correctly for the ``percent_complete`` field
across all metering-related and project response models.

Test Phases
-----------
1. Module Setup (imports)
2. MeteringData Model Tests
3. MeteringResponse Model Tests (GET /runs/metering)
4. CurrentMeteringResponse Model Tests (GET /runs/metering/current)
5. ProjectResponse Model Tests (GET /project)
6. Backward Compatibility Tests (ConfigDict extra="allow")
7. RunData Model Tests
8. Type Enforcement Tests (Cross-Model)
9. Parametrized Tests
10. Consistent Field Naming Test
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.models.metering import (
    CurrentMeteringResponse,
    MeteringData,
    MeteringResponse,
    RunData,
)
from src.models.project import ProjectData, ProjectResponse


# ---------------------------------------------------------------------------
# Phase 2: MeteringData Model Tests (Inline Metering Object)
# ---------------------------------------------------------------------------


class TestMeteringData:
    """Tests for the ``MeteringData`` model — the inline metering object."""

    def test_metering_data_valid_percent_complete(self) -> None:
        """MeteringData accepts a valid mid-range percent_complete value."""
        instance = MeteringData(percent_complete=75.5)
        assert instance.percent_complete == 75.5

    def test_metering_data_null_percent_complete(self) -> None:
        """MeteringData accepts an explicit ``None`` for percent_complete."""
        instance = MeteringData(percent_complete=None)
        assert instance.percent_complete is None

    def test_metering_data_default_percent_complete_is_none(self) -> None:
        """MeteringData defaults percent_complete to ``None`` when omitted."""
        instance = MeteringData()
        assert instance.percent_complete is None

    def test_metering_data_zero_percent_complete(self) -> None:
        """MeteringData accepts 0.0 — the minimum valid boundary value."""
        instance = MeteringData(percent_complete=0.0)
        assert instance.percent_complete == 0.0

    def test_metering_data_hundred_percent_complete(self) -> None:
        """MeteringData accepts 100.0 — the maximum valid boundary value."""
        instance = MeteringData(percent_complete=100.0)
        assert instance.percent_complete == 100.0

    def test_metering_data_rejects_above_100(self) -> None:
        """MeteringData rejects percent_complete > 100.0 (le=100.0)."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=100.1)

    def test_metering_data_rejects_below_zero(self) -> None:
        """MeteringData rejects percent_complete < 0.0 (ge=0.0)."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=-0.1)

    def test_metering_data_rejects_string_type(self) -> None:
        """MeteringData rejects string values for percent_complete."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete="50")

    def test_metering_data_with_additional_fields(self) -> None:
        """MeteringData correctly stores all metering fields together."""
        instance = MeteringData(
            percent_complete=50.0,
            estimated_hours_saved=5.2,
            estimated_lines_generated=1200,
        )
        assert instance.percent_complete == 50.0
        assert instance.estimated_hours_saved == 5.2
        assert instance.estimated_lines_generated == 1200

    def test_metering_data_integer_accepted_as_float(self) -> None:
        """MeteringData accepts an integer for percent_complete (Pydantic int-to-float coercion)."""
        instance = MeteringData(percent_complete=50)
        # Pydantic coerces int → float; the value should be accepted
        assert instance.percent_complete == 50
        # Verify it is functionally usable as a number
        assert 0.0 <= instance.percent_complete <= 100.0

    def test_metering_data_model_dump_json(self) -> None:
        """MeteringData.model_dump_json() includes percent_complete in JSON output."""
        instance = MeteringData(
            percent_complete=65.3,
            estimated_hours_saved=2.5,
            estimated_lines_generated=800,
        )
        json_str = instance.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["percent_complete"] == 65.3
        assert parsed["estimated_hours_saved"] == 2.5
        assert parsed["estimated_lines_generated"] == 800

    def test_metering_data_model_dump_includes_null_percent_complete(self) -> None:
        """MeteringData.model_dump() includes percent_complete key even when None."""
        instance = MeteringData()
        result = instance.model_dump()
        assert "percent_complete" in result
        assert result["percent_complete"] is None


# ---------------------------------------------------------------------------
# Phase 3: MeteringResponse Model Tests (GET /runs/metering)
# ---------------------------------------------------------------------------


class TestMeteringResponse:
    """Tests for the ``MeteringResponse`` model (GET /runs/metering)."""

    def test_metering_response_with_valid_data(self) -> None:
        """MeteringResponse stores percent_complete and empty runs list."""
        instance = MeteringResponse(runs=[], percent_complete=85.5)
        assert instance.percent_complete == 85.5
        assert instance.runs == []

    def test_metering_response_null_percent_complete(self) -> None:
        """MeteringResponse accepts ``None`` for percent_complete."""
        instance = MeteringResponse(runs=[], percent_complete=None)
        assert instance.percent_complete is None

    def test_metering_response_default_values(self) -> None:
        """MeteringResponse defaults both fields to ``None`` when omitted."""
        instance = MeteringResponse()
        assert instance.percent_complete is None
        assert instance.runs is None

    def test_metering_response_rejects_above_100(self) -> None:
        """MeteringResponse rejects percent_complete > 100 (le=100.0)."""
        with pytest.raises(ValidationError):
            MeteringResponse(percent_complete=101.0)

    def test_metering_response_rejects_below_zero(self) -> None:
        """MeteringResponse rejects percent_complete < 0 (ge=0.0)."""
        with pytest.raises(ValidationError):
            MeteringResponse(percent_complete=-1.0)

    def test_metering_response_with_run_data(self) -> None:
        """MeteringResponse correctly stores a list of RunData objects."""
        run1 = RunData(id="run-001", status="completed")
        run2 = RunData(id="run-002", status="in_progress")
        instance = MeteringResponse(
            runs=[run1, run2],
            percent_complete=60.0,
        )
        assert len(instance.runs) == 2
        assert instance.runs[0].id == "run-001"
        assert instance.runs[0].status == "completed"
        assert instance.runs[1].id == "run-002"
        assert instance.runs[1].status == "in_progress"
        assert instance.percent_complete == 60.0

    def test_metering_response_serialization_includes_percent_complete(self) -> None:
        """model_dump() always includes 'percent_complete' key, even when None."""
        result = MeteringResponse().model_dump()
        assert "percent_complete" in result
        assert result["percent_complete"] is None

    def test_metering_response_json_serialization(self) -> None:
        """model_dump_json() output contains the 'percent_complete' field name."""
        json_str = MeteringResponse(percent_complete=85.5).model_dump_json()
        assert "percent_complete" in json_str
        # Verify the JSON is valid and field value is correct
        parsed = json.loads(json_str)
        assert parsed["percent_complete"] == 85.5


# ---------------------------------------------------------------------------
# Phase 4: CurrentMeteringResponse Model Tests (GET /runs/metering/current)
# ---------------------------------------------------------------------------


class TestCurrentMeteringResponse:
    """Tests for ``CurrentMeteringResponse`` (GET /runs/metering/current)."""

    def test_current_metering_response_valid(self) -> None:
        """CurrentMeteringResponse accepts a valid mid-range percent_complete."""
        instance = CurrentMeteringResponse(percent_complete=42.0)
        assert instance.percent_complete == 42.0

    def test_current_metering_response_null_percent_complete(self) -> None:
        """CurrentMeteringResponse accepts ``None`` for percent_complete."""
        instance = CurrentMeteringResponse(percent_complete=None)
        assert instance.percent_complete is None

    def test_current_metering_response_with_current_run(self) -> None:
        """CurrentMeteringResponse stores a RunData object in currentRun."""
        run = RunData(
            id="run-active-001",
            status="in_progress",
            metering=MeteringData(percent_complete=42.0),
        )
        instance = CurrentMeteringResponse(
            currentRun=run,
            percent_complete=42.0,
        )
        assert instance.currentRun is not None
        assert instance.currentRun.id == "run-active-001"
        assert instance.currentRun.status == "in_progress"
        assert instance.currentRun.metering.percent_complete == 42.0
        assert instance.percent_complete == 42.0

    def test_current_metering_response_rejects_above_100(self) -> None:
        """CurrentMeteringResponse rejects percent_complete > 100."""
        with pytest.raises(ValidationError):
            CurrentMeteringResponse(percent_complete=100.1)

    def test_current_metering_response_rejects_below_zero(self) -> None:
        """CurrentMeteringResponse rejects percent_complete < 0."""
        with pytest.raises(ValidationError):
            CurrentMeteringResponse(percent_complete=-0.5)

    def test_current_metering_response_serialization_includes_percent_complete(self) -> None:
        """model_dump() always includes 'percent_complete' key, even when None."""
        result = CurrentMeteringResponse().model_dump()
        assert "percent_complete" in result
        assert result["percent_complete"] is None


# ---------------------------------------------------------------------------
# Phase 5: ProjectResponse Model Tests (GET /project)
# ---------------------------------------------------------------------------


class TestProjectResponse:
    """Tests for ``ProjectResponse`` with nested metering percent_complete."""

    def test_project_response_with_metering(self) -> None:
        """ProjectResponse exposes percent_complete via nested metering path."""
        metering = MeteringData(percent_complete=100.0)
        project_data = ProjectData(
            id="proj-1",
            name="Test Project",
            metering=metering,
        )
        response = ProjectResponse(project=project_data)
        assert response.project.metering.percent_complete == 100.0

    def test_project_response_null_metering_percent_complete(self) -> None:
        """ProjectResponse handles null percent_complete in nested metering."""
        metering = MeteringData(percent_complete=None)
        project_data = ProjectData(
            id="proj-2",
            name="Null Percent Project",
            metering=metering,
        )
        response = ProjectResponse(project=project_data)
        assert response.project.metering.percent_complete is None

    def test_project_response_null_metering_object(self) -> None:
        """ProjectData accepts ``None`` for the entire metering block."""
        project_data = ProjectData(
            id="proj-3",
            name="No Metering Project",
            metering=None,
        )
        response = ProjectResponse(project=project_data)
        assert response.project.metering is None

    def test_project_response_serialization_nested_percent_complete(self) -> None:
        """model_dump() preserves the nested percent_complete key in the dict."""
        metering = MeteringData(percent_complete=88.8)
        project_data = ProjectData(
            id="proj-4",
            name="Serialization Test Project",
            metering=metering,
        )
        response = ProjectResponse(project=project_data)
        result = response.model_dump()
        assert "percent_complete" in result["project"]["metering"]
        assert result["project"]["metering"]["percent_complete"] == 88.8

    def test_project_response_rejects_invalid_nested_percent_complete(self) -> None:
        """MeteringData nested inside ProjectResponse rejects value > 100."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=200.0)


# ---------------------------------------------------------------------------
# Phase 6: Backward Compatibility Tests (ConfigDict extra="allow")
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify all models accept unknown extra fields without errors."""

    def test_metering_data_accepts_extra_fields(self) -> None:
        """MeteringData with ConfigDict(extra='allow') accepts unknown keys."""
        instance = MeteringData(
            percent_complete=50.0,
            unknown_field="value",
        )
        assert instance.percent_complete == 50.0
        # The extra field should be accessible via model_dump
        dumped = instance.model_dump()
        assert dumped.get("unknown_field") == "value"

    def test_metering_response_accepts_extra_fields(self) -> None:
        """MeteringResponse with ConfigDict(extra='allow') accepts extra keys."""
        instance = MeteringResponse(
            percent_complete=50.0,
            extra_key=123,
        )
        assert instance.percent_complete == 50.0
        dumped = instance.model_dump()
        assert dumped.get("extra_key") == 123

    def test_current_metering_response_accepts_extra_fields(self) -> None:
        """CurrentMeteringResponse accepts unknown extra fields."""
        instance = CurrentMeteringResponse(
            percent_complete=30.0,
            some_other_field="test",
        )
        assert instance.percent_complete == 30.0
        dumped = instance.model_dump()
        assert dumped.get("some_other_field") == "test"

    def test_project_response_accepts_extra_fields(self) -> None:
        """ProjectResponse accepts unknown extra fields at the top level."""
        instance = ProjectResponse(
            project=None,
            api_version="v2",
        )
        dumped = instance.model_dump()
        assert dumped.get("api_version") == "v2"


# ---------------------------------------------------------------------------
# Phase 7: RunData Model Tests
# ---------------------------------------------------------------------------


class TestRunData:
    """Tests for the ``RunData`` model (individual run entries)."""

    def test_run_data_basic(self) -> None:
        """RunData stores basic id and status fields."""
        instance = RunData(id="run-1", status="completed")
        assert instance.id == "run-1"
        assert instance.status == "completed"
        assert instance.metering is None

    def test_run_data_with_metering(self) -> None:
        """RunData stores nested MeteringData with percent_complete."""
        metering = MeteringData(percent_complete=75.0)
        instance = RunData(
            id="run-2",
            status="in_progress",
            metering=metering,
        )
        assert instance.metering is not None
        assert instance.metering.percent_complete == 75.0

    def test_run_data_accepts_extra_fields(self) -> None:
        """RunData with ConfigDict(extra='allow') accepts unknown keys."""
        instance = RunData(
            id="run-3",
            status="completed",
            created_at="2026-04-01T12:00:00Z",
        )
        assert instance.id == "run-3"
        dumped = instance.model_dump()
        assert dumped.get("created_at") == "2026-04-01T12:00:00Z"


# ---------------------------------------------------------------------------
# Phase 8: Type Enforcement Tests (Cross-Model)
# ---------------------------------------------------------------------------


class TestTypeEnforcement:
    """Strict type enforcement — booleans, lists, dicts must be rejected."""

    def test_percent_complete_rejects_boolean(self) -> None:
        """MeteringData rejects ``True`` — booleans are not valid float values.

        Note: Pydantic 2.x default lax mode would coerce ``True`` → ``1.0``.
        The model's ``mode='before'`` field_validator explicitly rejects bools
        before Pydantic's coercion runs.
        """
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=True)

    def test_percent_complete_rejects_boolean_false(self) -> None:
        """MeteringData rejects ``False`` — booleans are not valid float values."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=False)

    def test_percent_complete_rejects_list(self) -> None:
        """MeteringData rejects a list for percent_complete."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=[50])

    def test_percent_complete_rejects_dict(self) -> None:
        """MeteringData rejects a dict for percent_complete."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete={"value": 50})


# ---------------------------------------------------------------------------
# Phase 9: Parametrized Tests
# ---------------------------------------------------------------------------


class TestParametrized:
    """Parametrized tests covering exhaustive valid, invalid, and type cases."""

    @pytest.mark.parametrize(
        "value",
        [0.0, 0.1, 1.0, 25.0, 50.0, 50.5, 75.0, 99.9, 100.0],
        ids=[
            "min_0.0",
            "near_min_0.1",
            "low_1.0",
            "quarter_25.0",
            "half_50.0",
            "mid_50.5",
            "three_quarter_75.0",
            "near_max_99.9",
            "max_100.0",
        ],
    )
    def test_percent_complete_valid_values(self, value: float) -> None:
        """MeteringData accepts all valid percent_complete values in [0.0, 100.0]."""
        instance = MeteringData(percent_complete=value)
        assert instance.percent_complete == value

    @pytest.mark.parametrize(
        "value",
        [-0.1, -1.0, 100.1, 200.0, 1000.0],
        ids=[
            "below_range_neg_0.1",
            "below_range_neg_1.0",
            "above_range_100.1",
            "above_range_200.0",
            "above_range_1000.0",
        ],
    )
    def test_percent_complete_invalid_values(self, value: float) -> None:
        """MeteringData rejects percent_complete values outside [0.0, 100.0]."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=value)

    @pytest.mark.parametrize(
        "value",
        ["50", "hello", True, False, [50], {"v": 50}],
        ids=[
            "string_numeric",
            "string_text",
            "bool_true",
            "bool_false",
            "list",
            "dict",
        ],
    )
    def test_percent_complete_invalid_types(self, value: object) -> None:
        """MeteringData rejects non-numeric types for percent_complete."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=value)


# ---------------------------------------------------------------------------
# Phase 10: Consistent Field Naming Test
# ---------------------------------------------------------------------------


class TestFieldNamingConsistency:
    """Verify all models use the EXACT field name ``percent_complete``."""

    def test_field_name_consistency_across_models(self) -> None:
        """All models with percent_complete use identical snake_case naming.

        Per AAP Goal 3: consistent naming across all endpoints — the field
        must be ``percent_complete`` (snake_case) everywhere.
        """
        assert "percent_complete" in MeteringData.model_fields, (
            "MeteringData is missing 'percent_complete' in model_fields"
        )
        assert "percent_complete" in MeteringResponse.model_fields, (
            "MeteringResponse is missing 'percent_complete' in model_fields"
        )
        assert "percent_complete" in CurrentMeteringResponse.model_fields, (
            "CurrentMeteringResponse is missing 'percent_complete' in model_fields"
        )
        # For ProjectResponse, percent_complete is nested inside MeteringData
        # (already checked above). Verify the nesting path exists.
        assert "metering" in ProjectData.model_fields, (
            "ProjectData is missing 'metering' in model_fields"
        )
        assert "project" in ProjectResponse.model_fields, (
            "ProjectResponse is missing 'project' in model_fields"
        )
