"""Integration tests for GET /project?id=xxx endpoint.

Validates the percent_complete field presence nested at project.metering.percent_complete,
value range, null handling, type enforcement, and backward compatibility
in the project response with inline metering data.
"""

import pytest
from pydantic import ValidationError

from src.api.project.project import get_project
from src.models.project import ProjectResponse, ProjectData
from src.models.metering import MeteringData
from conftest import make_project_response


# ---------------------------------------------------------------------------
# Phase 2: percent_complete field presence NESTED at project.metering
# ---------------------------------------------------------------------------


class TestPercentCompletePresentNested:
    """Verify percent_complete is nested at project.metering.percent_complete."""

    def test_percent_complete_present_in_nested_metering(
        self, mock_project_data: dict
    ) -> None:
        """percent_complete key must exist inside the metering object.

        AAP validation matrix: 'Field missing from response → classified as a bug.'
        CRITICAL: The field is NESTED inside project.metering, NOT at the
        top level of this endpoint's response.
        """
        # mock_project_data is shaped as the full response; extract the
        # inner project dict for the handler's project_data parameter.
        inner_project = mock_project_data["project"]
        response = get_project(
            project_id=inner_project.get("id"),
            project_data=inner_project,
        )
        response_dict = response.model_dump()
        metering = response_dict["project"]["metering"]
        assert "percent_complete" in metering, (
            "percent_complete key is missing from project.metering in "
            "the serialised response"
        )

    def test_percent_complete_not_at_top_level(
        self, mock_project_data: dict
    ) -> None:
        """percent_complete must NOT appear at the top level of the response.

        This is the ONLY endpoint where percent_complete is nested (the other
        two endpoints surface it at the top level).
        """
        inner_project = mock_project_data["project"]
        response = get_project(
            project_id=inner_project.get("id"),
            project_data=inner_project,
        )
        response_dict = response.model_dump()

        # Must NOT be a top-level key
        assert "percent_complete" not in response_dict, (
            "percent_complete should not be a top-level key in "
            "the project endpoint response"
        )

        # Must exist at the nested path
        nested_value = response_dict["project"]["metering"]["percent_complete"]
        assert nested_value is not None, (
            "percent_complete should have a non-None value when valid "
            "metering data is supplied"
        )


# ---------------------------------------------------------------------------
# Phase 3: Inline metering object contains the field
# ---------------------------------------------------------------------------


class TestMeteringObjectInProject:
    """Verify the inline metering object is present and properly structured."""

    def test_metering_object_present_in_project(self) -> None:
        """Metering object must exist when valid project data is provided."""
        response = get_project(
            project_data={
                "id": "proj-1",
                "name": "Test Project",
                "metering": {"current_index": 50, "total_steps": 100},
            }
        )
        assert response.project is not None, "project must not be None"
        assert response.project.metering is not None, (
            "project.metering must not be None when metering data is provided"
        )
        assert response.project.metering.percent_complete is not None, (
            "percent_complete must not be None when valid progress data exists"
        )

    def test_metering_object_structure(self) -> None:
        """Metering object must be a MeteringData instance with expected fields."""
        response = get_project(
            project_data={
                "id": "proj-struct",
                "name": "Structure Test",
                "metering": {
                    "current_index": 50,
                    "total_steps": 100,
                    "estimated_hours_saved": 3.5,
                    "estimated_lines_generated": 800,
                },
            }
        )
        metering = response.project.metering
        assert isinstance(metering, MeteringData), (
            f"metering must be a MeteringData instance, got {type(metering)}"
        )
        assert hasattr(metering, "percent_complete"), (
            "MeteringData must have a percent_complete attribute"
        )
        assert hasattr(metering, "estimated_hours_saved"), (
            "MeteringData must have an estimated_hours_saved attribute"
        )
        assert hasattr(metering, "estimated_lines_generated"), (
            "MeteringData must have an estimated_lines_generated attribute"
        )
        assert metering.estimated_hours_saved == 3.5
        assert metering.estimated_lines_generated == 800


# ---------------------------------------------------------------------------
# Phase 4: Null value when project has no metering data
# ---------------------------------------------------------------------------


class TestPercentCompleteNullHandling:
    """Verify null semantics when no metering data is available."""

    def test_percent_complete_null_when_no_metering_data(self) -> None:
        """percent_complete must be None when project_data is None.

        AAP validation: 'No data available → null'.
        """
        response = get_project(project_data=None)
        assert response.project is not None, (
            "project object must still exist even with no input data"
        )
        assert response.project.metering is not None, (
            "metering object must still exist (with null fields) even with "
            "no input data — field presence is mandatory"
        )
        assert response.project.metering.percent_complete is None, (
            "percent_complete must be None when no metering data is available"
        )

    def test_percent_complete_null_when_empty_project_data(self) -> None:
        """percent_complete must be None when project_data is an empty dict."""
        response = get_project(project_data={})
        assert response.project.metering.percent_complete is None, (
            "percent_complete must be None when project_data is {}"
        )

    def test_percent_complete_present_as_null_not_omitted(self) -> None:
        """percent_complete key must be PRESENT in the dict even when the value is null.

        The field is never silently omitted — it always appears in serialised
        output, set to ``None`` when no metering data is available.
        """
        response = get_project(project_data=None)
        response_dict = response.model_dump()
        metering_dict = response_dict["project"]["metering"]

        assert "percent_complete" in metering_dict, (
            "percent_complete key must be present in the serialised metering "
            "dict even when its value is null"
        )
        assert metering_dict["percent_complete"] is None, (
            "percent_complete value must be None, not some other falsy value"
        )

    def test_null_metering_consistency_with_fixture(
        self, mock_null_metering_data: dict
    ) -> None:
        """Null percent_complete is consistent between metering and project endpoints.

        Uses the mock_null_metering_data fixture to cross-reference the null
        pattern from the metering endpoint with the project endpoint's
        behaviour.
        """
        metering_null_value = mock_null_metering_data["percent_complete"]
        assert metering_null_value is None, (
            "mock_null_metering_data fixture must have percent_complete=None"
        )

        response = get_project(project_data=None)
        project_null_value = response.project.metering.percent_complete
        assert project_null_value is None, (
            "Project endpoint must also return None when no data is available"
        )


# ---------------------------------------------------------------------------
# Phase 5: Value range within nested structure
# ---------------------------------------------------------------------------


class TestPercentCompleteValueRange:
    """Verify percent_complete values within the valid 0.0–100.0 range."""

    def test_percent_complete_valid_range_completed(self) -> None:
        """Completed run: percent_complete == 100.0 when current_index == total_steps."""
        response = get_project(
            project_data={
                "id": "proj-done",
                "name": "Done Project",
                "metering": {"current_index": 100, "total_steps": 100},
            }
        )
        pct = response.project.metering.percent_complete
        assert pct == 100.0, (
            f"Expected percent_complete == 100.0, got {pct}"
        )
        assert 0.0 <= pct <= 100.0, (
            f"percent_complete {pct} is outside the valid range [0.0, 100.0]"
        )

    def test_percent_complete_valid_range_partial(self) -> None:
        """In-progress run: percent_complete reflects partial progress (75/100)."""
        response = get_project(
            project_data={
                "id": "proj-partial",
                "name": "Partial Project",
                "metering": {"current_index": 75, "total_steps": 100},
            }
        )
        pct = response.project.metering.percent_complete
        assert pct == 75.0, (
            f"Expected percent_complete == 75.0, got {pct}"
        )
        assert 0.0 <= pct <= 100.0, (
            f"percent_complete {pct} is outside the valid range [0.0, 100.0]"
        )

    def test_percent_complete_valid_range_zero(self) -> None:
        """Zero progress: percent_complete == 0.0 when current_index == 0."""
        response = get_project(
            project_data={
                "id": "proj-zero",
                "name": "Zero Project",
                "metering": {"current_index": 0, "total_steps": 100},
            }
        )
        pct = response.project.metering.percent_complete
        assert pct == 0.0, (
            f"Expected percent_complete == 0.0, got {pct}"
        )

    def test_percent_complete_mid_range_from_factory(self) -> None:
        """Verify a mid-range value using make_project_response factory."""
        factory_data = make_project_response(percent_complete=42.5)
        inner_project = factory_data["project"]
        response = get_project(
            project_id=inner_project["id"],
            project_data=inner_project,
        )
        pct = response.project.metering.percent_complete
        assert pct == 42.5, (
            f"Expected percent_complete == 42.5, got {pct}"
        )
        assert 0.0 <= pct <= 100.0


# ---------------------------------------------------------------------------
# Phase 6: Type validation
# ---------------------------------------------------------------------------


class TestPercentCompleteTypeValidation:
    """Verify type correctness of percent_complete values."""

    def test_percent_complete_is_float_when_present(self) -> None:
        """percent_complete must be a float when not None.

        AAP requirement: 'must be float or null'.
        """
        response = get_project(
            project_data={
                "id": "proj-type",
                "name": "Type Test",
                "metering": {"current_index": 50, "total_steps": 100},
            }
        )
        pct = response.project.metering.percent_complete
        assert pct is not None, "Expected non-None value for this test case"
        assert isinstance(pct, float), (
            f"percent_complete must be a float, got {type(pct).__name__}"
        )

    def test_percent_complete_is_none_not_other_falsy_values(self) -> None:
        """When no data, percent_complete must be exactly None — not 0, '', or False."""
        response = get_project(project_data=None)
        pct = response.project.metering.percent_complete
        assert pct is None, (
            f"percent_complete must be None, got {pct!r}"
        )
        # Explicit checks against other falsy values
        assert pct != 0, "percent_complete must not be 0 when no data is available"
        assert pct != "", "percent_complete must not be empty string"
        assert pct is not False, "percent_complete must not be False"


# ---------------------------------------------------------------------------
# Phase 7: Backward compatibility of project response
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify backward compatibility of the project response structure."""

    def test_backward_compatibility_project_fields_preserved(self) -> None:
        """All existing project-level fields (id, name) must be preserved.

        AAP requirement: 'All existing response fields must be preserved.'
        """
        response = get_project(
            project_data={
                "id": "proj-compat",
                "name": "Compat Project",
                "metering": {"current_index": 100, "total_steps": 100},
                "custom_extra_field": "should_be_preserved",
            }
        )
        response_dict = response.model_dump()
        project_dict = response_dict["project"]

        assert project_dict["id"] == "proj-compat", (
            "Project id must be preserved"
        )
        assert project_dict["name"] == "Compat Project", (
            "Project name must be preserved"
        )
        assert "metering" in project_dict, (
            "Metering object must be present"
        )
        assert project_dict["metering"]["percent_complete"] == 100.0, (
            "percent_complete must be present in metering"
        )

    def test_response_is_project_response_model(self) -> None:
        """Handler must return a ProjectResponse Pydantic model, not a raw dict."""
        response = get_project(
            project_data={
                "id": "proj-model",
                "name": "Model Test",
                "metering": {"current_index": 50, "total_steps": 100},
            }
        )
        assert isinstance(response, ProjectResponse), (
            f"get_project must return a ProjectResponse, got {type(response).__name__}"
        )
        assert isinstance(response.project, ProjectData), (
            f"response.project must be a ProjectData, "
            f"got {type(response.project).__name__}"
        )

    def test_project_data_allows_extra_fields(self) -> None:
        """ProjectData with ConfigDict(extra='allow') must accept unknown fields.

        This ensures backward compatibility: if the API adds new fields in the
        future, existing models do not reject them.
        """
        project = ProjectData(
            id="proj-extra",
            name="Extra Fields Test",
            metering=MeteringData(percent_complete=50.0),
            some_extra_field="extra_value",
            another_extra=42,
        )
        dumped = project.model_dump()
        assert dumped["id"] == "proj-extra"
        assert dumped["name"] == "Extra Fields Test"
        assert dumped["metering"]["percent_complete"] == 50.0
        assert dumped["some_extra_field"] == "extra_value", (
            "Extra fields must be preserved via ConfigDict(extra='allow')"
        )
        assert dumped["another_extra"] == 42, (
            "Extra integer fields must be preserved"
        )

    def test_backward_compat_extra_fields_from_handler(self) -> None:
        """Extra fields passed through project_data are preserved in the response."""
        response = get_project(
            project_data={
                "id": "proj-pass",
                "name": "Pass-through",
                "metering": {"percent_complete": 80.0},
                "deployment_env": "production",
                "version": 3,
            }
        )
        response_dict = response.model_dump()
        project_dict = response_dict["project"]
        assert project_dict.get("deployment_env") == "production", (
            "Extra project-level field 'deployment_env' must be preserved"
        )
        assert project_dict.get("version") == 3, (
            "Extra project-level field 'version' must be preserved"
        )


# ---------------------------------------------------------------------------
# Phase 8: Model validation (Pydantic on nested MeteringData)
# ---------------------------------------------------------------------------


class TestModelValidation:
    """Verify Pydantic model validation for MeteringData percent_complete constraints."""

    def test_metering_data_rejects_percent_above_100(self) -> None:
        """MeteringData must raise ValidationError for percent_complete > 100.0.

        AAP validation matrix: 'Value > 100 → Bug'.
        """
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=100.1)

    def test_metering_data_rejects_percent_below_zero(self) -> None:
        """MeteringData must raise ValidationError for percent_complete < 0.0.

        AAP validation matrix: 'Value < 0 → Bug'.
        """
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=-0.1)

    def test_metering_data_rejects_string_type(self) -> None:
        """MeteringData must raise ValidationError for string percent_complete.

        AAP validation matrix: 'Wrong data type → Bug'.
        """
        with pytest.raises(ValidationError):
            MeteringData(percent_complete="50")

    def test_metering_data_rejects_boolean_type(self) -> None:
        """MeteringData must reject boolean values despite bool being a subclass of int."""
        with pytest.raises(ValidationError):
            MeteringData(percent_complete=True)

    def test_metering_data_accepts_none(self) -> None:
        """MeteringData must accept None for percent_complete (null is valid)."""
        metering = MeteringData(percent_complete=None)
        assert metering.percent_complete is None

    def test_metering_data_accepts_zero(self) -> None:
        """MeteringData must accept 0.0 as a valid percent_complete value."""
        metering = MeteringData(percent_complete=0.0)
        assert metering.percent_complete == 0.0

    def test_metering_data_accepts_hundred(self) -> None:
        """MeteringData must accept 100.0 as a valid percent_complete value."""
        metering = MeteringData(percent_complete=100.0)
        assert metering.percent_complete == 100.0

    def test_metering_data_accepts_integer_as_float(self) -> None:
        """MeteringData must accept integer values (coerced to float)."""
        metering = MeteringData(percent_complete=50)
        assert metering.percent_complete == 50.0
        assert isinstance(metering.percent_complete, float)

    def test_metering_data_model_dump_includes_percent_complete(self) -> None:
        """model_dump() output must include the percent_complete key."""
        metering = MeteringData(percent_complete=75.0)
        dumped = metering.model_dump()
        assert "percent_complete" in dumped
        assert dumped["percent_complete"] == 75.0

    def test_metering_data_model_dump_includes_null_percent_complete(self) -> None:
        """model_dump() output must include percent_complete even when None."""
        metering = MeteringData(percent_complete=None)
        dumped = metering.model_dump()
        assert "percent_complete" in dumped
        assert dumped["percent_complete"] is None


# ---------------------------------------------------------------------------
# Phase 9: Consistent field naming
# ---------------------------------------------------------------------------


class TestConsistentFieldNaming:
    """Verify consistent snake_case field naming for percent_complete."""

    def test_field_name_is_percent_complete_snake_case(self) -> None:
        """Field must be 'percent_complete' (snake_case), never 'percentComplete'.

        AAP Goal 3: Consistent naming across all endpoints.
        """
        response = get_project(
            project_data={
                "id": "proj-naming",
                "name": "Naming Test",
                "metering": {"current_index": 50, "total_steps": 100},
            }
        )
        response_dict = response.model_dump()
        metering_dict = response_dict["project"]["metering"]

        assert "percent_complete" in metering_dict, (
            "percent_complete (snake_case) must be present in serialised output"
        )
        assert "percentComplete" not in metering_dict, (
            "percentComplete (camelCase) must NOT appear — AAP Goal 3 "
            "requires consistent snake_case naming"
        )

    def test_field_name_consistent_in_model_fields(self) -> None:
        """The MeteringData Pydantic model must declare the field as 'percent_complete'."""
        field_names = set(MeteringData.model_fields.keys())
        assert "percent_complete" in field_names, (
            "MeteringData model must declare 'percent_complete' field"
        )
        assert "percentComplete" not in field_names, (
            "MeteringData model must NOT declare 'percentComplete' field"
        )

    def test_field_name_in_factory_output(self) -> None:
        """make_project_response factory must use 'percent_complete' naming."""
        factory_output = make_project_response(percent_complete=60.0)
        metering = factory_output["project"]["metering"]
        assert "percent_complete" in metering
        assert "percentComplete" not in metering
