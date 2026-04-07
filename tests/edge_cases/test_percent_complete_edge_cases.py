"""Edge case tests for percent_complete field validation.

Comprehensive test suite exercising the ``validate_percent_complete()`` function
from ``src.validators.percent_complete`` against the AAP validation matrix
(Section 0.7.2).  Covers:

* Boundary values — 0.0 (minimum valid) and 100.0 (maximum valid)
* Mid-range happy path — 50.5
* Null / ``None`` handling — valid "no data available" scenario
* Out-of-range rejection — values below 0.0 or above 100.0
* Type enforcement — ``str``, ``bool``, ``list``, ``dict`` all rejected
* Integer-to-float coercion — ``50`` → ``50.0``
* Parametrized sweep — via ``boundary_values`` fixture from ``conftest.py``
* Error message validation — descriptive messages include offending value / type

All tests target the pure validator function directly — no HTTP mocking or
service-layer setup is needed.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from src.validators.percent_complete import validate_percent_complete


# ---------------------------------------------------------------------------
# Phase 2 — Boundary Value Tests (per AAP validation matrix)
# ---------------------------------------------------------------------------


class TestBoundaryValues:
    """Tests for the exact boundaries of the 0.0–100.0 valid range."""

    def test_minimum_boundary_zero(self) -> None:
        """0.0 is the minimum valid percent_complete value."""
        result = validate_percent_complete(0.0)
        assert result == 0.0, f"Expected 0.0, got {result}"
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"

    def test_maximum_boundary_hundred(self) -> None:
        """100.0 is the maximum valid percent_complete value."""
        result = validate_percent_complete(100.0)
        assert result == 100.0, f"Expected 100.0, got {result}"
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"

    def test_mid_range_value(self) -> None:
        """50.5 is a valid mid-range percent_complete value (happy path)."""
        result = validate_percent_complete(50.5)
        assert result == 50.5, f"Expected 50.5, got {result}"
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"

    def test_small_valid_value(self) -> None:
        """0.001 is a valid percent_complete just above the minimum."""
        result = validate_percent_complete(0.001)
        assert result == 0.001
        assert isinstance(result, float)

    def test_near_max_valid_value(self) -> None:
        """99.999 is a valid percent_complete just below the maximum."""
        result = validate_percent_complete(99.999)
        assert result == 99.999
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Phase 3 — Null Handling Tests
# ---------------------------------------------------------------------------


class TestNullHandling:
    """Tests for ``None`` as a valid percent_complete input.

    Per AAP: when no metering data is available, percent_complete is ``None``.
    """

    def test_null_accepted(self) -> None:
        """None is a valid input representing 'no data available'."""
        result = validate_percent_complete(None)
        assert result is None, f"Expected None, got {result!r}"

    def test_null_returns_none_not_zero(self) -> None:
        """None must return None — not be coerced to 0.0."""
        result = validate_percent_complete(None)
        assert result is None
        assert result != 0.0  # explicitly verify no zero-coercion


# ---------------------------------------------------------------------------
# Phase 4 — Out-of-Range Rejection Tests (per AAP: out-of-range = BUG)
# ---------------------------------------------------------------------------


class TestOutOfRangeRejection:
    """Tests verifying that values outside [0.0, 100.0] raise ``ValueError``."""

    def test_rejects_slightly_above_max(self) -> None:
        """100.1 is rejected — exceeds the 100.0 maximum."""
        with pytest.raises(ValueError):
            validate_percent_complete(100.1)

    def test_rejects_slightly_below_min(self) -> None:
        """-0.1 is rejected — below the 0.0 minimum."""
        with pytest.raises(ValueError):
            validate_percent_complete(-0.1)

    def test_rejects_large_negative(self) -> None:
        """-1.0 is rejected — well below range."""
        with pytest.raises(ValueError):
            validate_percent_complete(-1.0)

    def test_rejects_large_above_max(self) -> None:
        """200.0 is rejected — well above range."""
        with pytest.raises(ValueError):
            validate_percent_complete(200.0)

    def test_rejects_very_large_value(self) -> None:
        """1_000_000.0 is rejected — extreme out-of-range."""
        with pytest.raises(ValueError):
            validate_percent_complete(1_000_000.0)

    def test_rejects_very_large_negative_value(self) -> None:
        """-1_000_000.0 is rejected — extreme negative."""
        with pytest.raises(ValueError):
            validate_percent_complete(-1_000_000.0)


# ---------------------------------------------------------------------------
# Phase 5 — Type Enforcement Tests (per AAP: wrong type = BUG)
# ---------------------------------------------------------------------------


class TestTypeEnforcement:
    """Tests verifying that non-numeric types raise ``TypeError``.

    CRITICAL: ``bool`` must be rejected even though ``isinstance(True, int)``
    evaluates to ``True`` in Python.  The validator checks for ``bool`` before
    checking ``int``/``float``.
    """

    def test_rejects_string_type(self) -> None:
        """String '50' is rejected — even though it looks numeric."""
        with pytest.raises(TypeError):
            validate_percent_complete("50")

    def test_rejects_non_numeric_string(self) -> None:
        """Non-numeric string 'hello' is rejected."""
        with pytest.raises(TypeError):
            validate_percent_complete("hello")

    def test_rejects_empty_string(self) -> None:
        """Empty string is rejected."""
        with pytest.raises(TypeError):
            validate_percent_complete("")

    def test_rejects_boolean_true(self) -> None:
        """Boolean True is rejected — not treated as integer 1.

        CRITICAL: ``bool`` is a subclass of ``int`` in Python, so the
        validator must check for ``bool`` BEFORE ``int``/``float``.
        """
        with pytest.raises(TypeError):
            validate_percent_complete(True)

    def test_rejects_boolean_false(self) -> None:
        """Boolean False is rejected — not treated as integer 0."""
        with pytest.raises(TypeError):
            validate_percent_complete(False)

    def test_rejects_list_type(self) -> None:
        """List [50.0] is rejected."""
        with pytest.raises(TypeError):
            validate_percent_complete([50.0])

    def test_rejects_dict_type(self) -> None:
        """Dict {'value': 50} is rejected."""
        with pytest.raises(TypeError):
            validate_percent_complete({"value": 50})

    def test_rejects_tuple_type(self) -> None:
        """Tuple (50.0,) is rejected."""
        with pytest.raises(TypeError):
            validate_percent_complete((50.0,))

    def test_rejects_set_type(self) -> None:
        """Set {50.0} is rejected."""
        with pytest.raises(TypeError):
            validate_percent_complete({50.0})

    def test_rejects_bytes_type(self) -> None:
        """Bytes b'50' is rejected."""
        with pytest.raises(TypeError):
            validate_percent_complete(b"50")


# ---------------------------------------------------------------------------
# Phase 6 — Integer-to-Float Coercion Tests
# ---------------------------------------------------------------------------


class TestIntegerToFloatCoercion:
    """Tests verifying that valid ``int`` inputs are coerced to ``float``."""

    def test_integer_accepted_as_float(self) -> None:
        """Integer 50 is accepted and coerced to 50.0."""
        result = validate_percent_complete(50)
        assert result == 50.0, f"Expected 50.0, got {result}"
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"

    def test_integer_zero_accepted(self) -> None:
        """Integer 0 is accepted and coerced to 0.0."""
        result = validate_percent_complete(0)
        assert result == 0.0, f"Expected 0.0, got {result}"
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"

    def test_integer_hundred_accepted(self) -> None:
        """Integer 100 is accepted and coerced to 100.0."""
        result = validate_percent_complete(100)
        assert result == 100.0, f"Expected 100.0, got {result}"
        assert isinstance(result, float), f"Expected float, got {type(result).__name__}"

    def test_integer_one_accepted(self) -> None:
        """Integer 1 is accepted and coerced to 1.0."""
        result = validate_percent_complete(1)
        assert result == 1.0
        assert isinstance(result, float)

    def test_integer_ninety_nine_accepted(self) -> None:
        """Integer 99 is accepted and coerced to 99.0."""
        result = validate_percent_complete(99)
        assert result == 99.0
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Phase 7 — Parametrized Boundary Test Using Fixture from conftest.py
# ---------------------------------------------------------------------------


class TestParametrizedBoundary:
    """Parametrized sweep of the full validation matrix using ``boundary_values``."""

    def test_boundary_values_parametrized(
        self, boundary_values: List[Tuple[object, bool]]
    ) -> None:
        """Exercise every (value, is_valid) tuple from the boundary_values fixture.

        The ``boundary_values`` fixture (from ``conftest.py``, session scope)
        returns a list of tuples:

        - ``(0.0, True)``     — minimum valid
        - ``(100.0, True)``   — maximum valid
        - ``(50.5, True)``    — mid-range valid
        - ``(None, True)``    — null is valid
        - ``(50, True)``      — integer accepted (int→float coercion)
        - ``(-0.1, False)``   — below range
        - ``(100.1, False)``  — above range
        - ``("50", False)``   — string type
        - ``(True, False)``   — boolean type

        For valid values we assert no exception is raised and the return type
        is correct.  For invalid values we assert ``ValueError`` or
        ``TypeError`` is raised.
        """
        for value, is_valid in boundary_values:
            if is_valid:
                # Valid input — must not raise and must return the right type
                result = validate_percent_complete(value)
                if value is None:
                    assert result is None, (
                        f"Expected None for input None, got {result!r}"
                    )
                else:
                    assert isinstance(result, float), (
                        f"Expected float for input {value!r}, "
                        f"got {type(result).__name__}"
                    )
            else:
                # Invalid input — must raise ValueError or TypeError
                with pytest.raises((ValueError, TypeError)):
                    validate_percent_complete(value)


# ---------------------------------------------------------------------------
# Phase 8 — Error Message Validation Tests
# ---------------------------------------------------------------------------


class TestErrorMessageValidation:
    """Tests that error messages are descriptive and include relevant details."""

    def test_value_error_message_includes_value(self) -> None:
        """ValueError for 150.0 should mention the offending value and valid range."""
        with pytest.raises(ValueError, match=r"150\.0"):
            validate_percent_complete(150.0)

    def test_value_error_message_mentions_range_bounds(self) -> None:
        """ValueError message should reference both 0.0 and 100.0 range limits."""
        with pytest.raises(ValueError) as exc_info:
            validate_percent_complete(150.0)
        error_msg = str(exc_info.value)
        assert "0.0" in error_msg, f"Expected '0.0' in error message: {error_msg}"
        assert "100.0" in error_msg, f"Expected '100.0' in error message: {error_msg}"

    def test_type_error_message_includes_type_name(self) -> None:
        """TypeError for 'test' should mention the type name 'str'."""
        with pytest.raises(TypeError, match=r"str"):
            validate_percent_complete("test")

    def test_type_error_message_includes_bool_type_name(self) -> None:
        """TypeError for True should mention the type name 'bool'."""
        with pytest.raises(TypeError, match=r"bool"):
            validate_percent_complete(True)

    def test_value_error_message_for_negative(self) -> None:
        """ValueError for -5.0 should mention the offending value."""
        with pytest.raises(ValueError, match=r"-5\.0"):
            validate_percent_complete(-5.0)

    def test_type_error_message_for_list(self) -> None:
        """TypeError for list input should mention the type name 'list'."""
        with pytest.raises(TypeError, match=r"list"):
            validate_percent_complete([1, 2, 3])

    def test_type_error_message_for_dict(self) -> None:
        """TypeError for dict input should mention the type name 'dict'."""
        with pytest.raises(TypeError, match=r"dict"):
            validate_percent_complete({"key": "value"})
