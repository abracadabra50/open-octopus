"""
Open Octopus - Modern Python client for the Octopus Energy API.

Supports the full GraphQL/Kraken API including:
- Live power consumption (Home Mini)
- Intelligent Octopus dispatch slots
- Saving Sessions / Free Electricity events
- Account balance and tariff info
- macOS menu bar app
- Claude AI agent for natural language queries

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

Natural language queries:
    >>> from open_octopus import OctopusAgent
    >>>
    >>> agent = OctopusAgent()
    >>> response = await agent.ask("What's my current power usage?")
    >>> print(response)
"""

__version__ = "0.3.0"

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
    GasConsumption,
    Tariff,
    GasTariff,
    Rate,
    Dispatch,
    DispatchStatus,
    SavingSession,
    LivePower,
    SmartDevice,
    MeterPoint,
    GasMeterPoint,
)

# Optional imports for extras
try:
    from .agent import OctopusAgent
except ImportError:
    OctopusAgent = None

try:
    from .menubar import OctopusMenuBar
except ImportError:
    OctopusMenuBar = None

__all__ = [
    # Client
    "OctopusClient",
    # Exceptions
    "OctopusError",
    "AuthenticationError",
    "APIError",
    "ConfigurationError",
    # Electricity Models
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
    # Gas Models
    "GasConsumption",
    "GasTariff",
    "GasMeterPoint",
    # Optional
    "OctopusAgent",
    "OctopusMenuBar",
]
