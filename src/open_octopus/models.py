"""Data models for Open Octopus API responses."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    """Octopus Energy account information."""
    number: str
    balance: float  # GBP (negative = credit)
    name: str
    status: str
    address: str


@dataclass
class Consumption:
    """Half-hourly electricity consumption reading."""
    start: datetime
    end: datetime
    kwh: float


@dataclass
class GasConsumption:
    """Half-hourly gas consumption reading."""
    start: datetime
    end: datetime
    kwh: float  # Energy in kWh (converted from m³ if needed)
    m3: Optional[float] = None  # Volume in cubic meters (SMETS2 meters)


@dataclass
class Tariff:
    """Electricity tariff details."""
    name: str
    product_code: str
    standing_charge: float  # pence/day
    rates: dict[str, float]  # rate_name -> pence/kWh

    # For time-of-use tariffs like Intelligent Octopus Go
    off_peak_rate: Optional[float] = None  # pence/kWh
    peak_rate: Optional[float] = None  # pence/kWh
    off_peak_start: Optional[str] = None  # "23:30"
    off_peak_end: Optional[str] = None  # "05:30"


@dataclass
class Rate:
    """Current electricity rate with time-of-use info."""
    rate: float  # pence/kWh
    is_off_peak: bool
    period_end: datetime
    next_rate: float


@dataclass
class Dispatch:
    """Intelligent Octopus dispatch (smart charging window)."""
    start: datetime
    end: datetime
    source: str  # "smart-charge" or "bump-charge"

    @property
    def duration_minutes(self) -> int:
        """Get dispatch duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)


@dataclass
class DispatchStatus:
    """Current dispatch status - are we charging?"""
    is_dispatching: bool
    current_dispatch: Optional[Dispatch] = None
    next_dispatch: Optional[Dispatch] = None


@dataclass
class SavingSession:
    """Saving Session / Free Electricity event."""
    code: str
    start: datetime
    end: datetime
    reward_per_kwh: int  # Octopoints per kWh saved

    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        now = datetime.now(self.start.tzinfo)
        return self.start <= now <= self.end

    @property
    def is_upcoming(self) -> bool:
        """Check if session is in the future."""
        now = datetime.now(self.start.tzinfo)
        return self.start > now


@dataclass
class LivePower:
    """Real-time power consumption from Home Mini."""
    demand_watts: int
    read_at: datetime
    consumption_kwh: Optional[float] = None

    @property
    def demand_kw(self) -> float:
        """Get demand in kilowatts."""
        return self.demand_watts / 1000


@dataclass
class SmartDevice:
    """Registered smart device (EV, battery, etc)."""
    device_id: str
    provider: str  # "OHME", "TESLA", etc
    model: Optional[str] = None
    status: str = "ACTIVE"


@dataclass
class MeterPoint:
    """Electricity meter point."""
    mpan: str
    meter_serial: str
    is_smart: bool
    supplier: str


@dataclass
class GasMeterPoint:
    """Gas meter point."""
    mprn: str
    meter_serial: str
    is_smart: bool
    supplier: str


@dataclass
class GasTariff:
    """Gas tariff details."""
    name: str
    product_code: str
    standing_charge: float  # pence/day
    unit_rate: float  # pence/kWh
