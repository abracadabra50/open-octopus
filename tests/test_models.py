"""Tests for data models."""

from datetime import datetime, timezone
from open_octopus import (
    Account, Consumption, Tariff, Rate, Dispatch, DispatchStatus,
    SavingSession, LivePower
)


def test_account():
    """Test Account model."""
    acc = Account(
        number="A-12345678",
        balance=-150.50,
        name="John Smith",
        status="ACTIVE",
        address="123 Test Street"
    )
    assert acc.balance == -150.50
    assert acc.number == "A-12345678"


def test_consumption():
    """Test Consumption model."""
    c = Consumption(
        start=datetime(2024, 1, 1, 0, 0),
        end=datetime(2024, 1, 1, 0, 30),
        kwh=0.5
    )
    assert c.kwh == 0.5


def test_dispatch_duration():
    """Test Dispatch duration calculation."""
    d = Dispatch(
        start=datetime(2024, 1, 1, 23, 30),
        end=datetime(2024, 1, 2, 5, 30),
        source="smart-charge"
    )
    assert d.duration_minutes == 360  # 6 hours


def test_live_power():
    """Test LivePower model."""
    p = LivePower(
        demand_watts=1500,
        read_at=datetime.now(timezone.utc)
    )
    assert p.demand_kw == 1.5


def test_saving_session_active():
    """Test SavingSession active/upcoming detection."""
    now = datetime.now(timezone.utc)

    # Past session
    past = SavingSession(
        code="TEST1",
        start=datetime(2020, 1, 1, 14, 0, tzinfo=timezone.utc),
        end=datetime(2020, 1, 1, 15, 0, tzinfo=timezone.utc),
        reward_per_kwh=800
    )
    assert not past.is_active
    assert not past.is_upcoming
