"""
Open Octopus - Modern Python client for the Octopus Energy API.

Supports the full GraphQL/Kraken API including:
- Live power consumption (Home Mini)
- Intelligent Octopus dispatch slots
- Saving Sessions / Free Electricity events
- Account balance and tariff info

Example:
    >>> from open_octopus import OctopusClient
    >>>
    >>> async with OctopusClient(api_key="sk_live_xxx", account="A-1234") as client:
    ...     account = await client.get_account()
    ...     print(f"Balance: £{account.balance:.2f}")
    ...
    ...     power = await client.get_live_power()
    ...     if power:
    ...         print(f"Current: {power.demand_kw:.2f} kW")
"""

__version__ = "0.1.0"

from .client import (
    OctopusClient,
    OctopusError,
    AuthenticationError,
    APIError,
    ConfigurationError,
)
from .models import (
    Account,
    Consumption,
    Tariff,
    Rate,
    Dispatch,
    DispatchStatus,
    SavingSession,
    LivePower,
    SmartDevice,
    MeterPoint,
)

__all__ = [
    # Client
    "OctopusClient",
    # Exceptions
    "OctopusError",
    "AuthenticationError",
    "APIError",
    "ConfigurationError",
    # Models
    "Account",
    "Consumption",
    "Tariff",
    "Rate",
    "Dispatch",
    "DispatchStatus",
    "SavingSession",
    "LivePower",
    "SmartDevice",
    "MeterPoint",
]
