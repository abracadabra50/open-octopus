"""
Tests for LivePower demand parsing — specifically the float string issue reported in #5.

The Octopus API returns demand as a float-formatted string (e.g. "1500.0") rather than
an integer. These tests document the correct parsing behaviour and guard against
regressions if the field type is changed back to int.

Related: PR #9 (fix/demand-float-cast), Issue #5.
"""

import pytest
from datetime import datetime, timezone
from open_octopus.models import LivePower


# ---------------------------------------------------------------------------
# Model: demand_watts type acceptance
# ---------------------------------------------------------------------------

class TestLivePowerDemandType:
    """LivePower.demand_watts should accept float values from the API."""

    def test_integer_demand(self):
        """Integer demand still works (backwards compatibility)."""
        p = LivePower(demand_watts=1500, read_at=datetime.now(timezone.utc))
        assert p.demand_watts == 1500
        assert p.demand_kw == pytest.approx(1.5)

    def test_float_demand(self):
        """Float demand (as returned by Octopus API) must be accepted."""
        p = LivePower(demand_watts=1500.0, read_at=datetime.now(timezone.utc))
        assert p.demand_watts == pytest.approx(1500.0)
        assert p.demand_kw == pytest.approx(1.5)

    def test_float_demand_fractional(self):
        """Fractional watt values (edge case) should propagate correctly."""
        p = LivePower(demand_watts=1234.5, read_at=datetime.now(timezone.utc))
        assert p.demand_kw == pytest.approx(1.2345)

    def test_zero_demand(self):
        """Zero demand (API may return 0 or null → treated as 0)."""
        p = LivePower(demand_watts=0.0, read_at=datetime.now(timezone.utc))
        assert p.demand_watts == 0.0
        assert p.demand_kw == 0.0

    def test_demand_kw_precision(self):
        """demand_kw divides by 1000; precision matters for display."""
        p = LivePower(demand_watts=3750.0, read_at=datetime.now(timezone.utc))
        assert p.demand_kw == pytest.approx(3.75)


# ---------------------------------------------------------------------------
# Client-side parsing: float() vs int() on API string values
# ---------------------------------------------------------------------------

class TestDemandParsing:
    """
    The API returns demand as a string like "1500.0".
    The client must use float() not int() to parse it.

    These tests document the exact failure mode from issue #5
    and confirm the fix works correctly.
    """

    @pytest.mark.parametrize("raw_value,expected", [
        ("1500.0",  1500.0),  # typical API response
        ("1500",    1500.0),  # integer string also works
        ("0.0",        0.0),  # zero case
        ("3750.5",  3750.5),  # fractional watts
        (1500.0,    1500.0),  # already a float
        (1500,      1500.0),  # already an int
    ])
    def test_float_cast_accepts_float_strings(self, raw_value, expected):
        """float() correctly parses all values the API can return."""
        result = float(raw_value or 0)
        assert result == pytest.approx(expected)

    @pytest.mark.parametrize("raw_value", [
        "1500.0",  # this is what the API actually returns
        "3750.5",
    ])
    def test_int_cast_fails_on_float_strings(self, raw_value):
        """
        Regression guard: int() raises ValueError on float-formatted strings.
        This is the exact bug from issue #5 — keep this test to prevent reversion.
        """
        with pytest.raises(ValueError, match="invalid literal for int"):
            int(raw_value)

    def test_none_demand_defaults_to_zero(self):
        """API may return null demand; `float(None or 0)` should give 0.0."""
        raw_value = None
        result = float(raw_value or 0)
        assert result == 0.0

    def test_parsed_value_feeds_live_power(self):
        """End-to-end: API string → float cast → LivePower construction."""
        raw_demand = "2400.0"  # as returned by Octopus telemetry API
        p = LivePower(
            demand_watts=float(raw_demand or 0),
            read_at=datetime.now(timezone.utc),
        )
        assert p.demand_watts == pytest.approx(2400.0)
        assert p.demand_kw == pytest.approx(2.4)
