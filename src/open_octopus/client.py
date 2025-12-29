"""Async client for the Octopus Energy GraphQL API."""

import httpx
from datetime import datetime, timedelta
from typing import Optional

from .models import (
    Account, Consumption, GasConsumption, Tariff, GasTariff, Rate,
    Dispatch, DispatchStatus, SavingSession, LivePower, SmartDevice,
    MeterPoint, GasMeterPoint
)


GRAPHQL_URL = "https://api.octopus.energy/v1/graphql/"
REST_API_URL = "https://api.octopus.energy/v1"


class OctopusClient:
    """
    Async client for Octopus Energy's GraphQL (Kraken) API.

    Supports features not available in the REST API:
    - Live power consumption (requires Home Mini)
    - Intelligent Octopus dispatch slots
    - Saving Sessions / Free Electricity events
    - Account balance and status

    Example:
        >>> async with OctopusClient(api_key="sk_live_xxx", account="A-1234") as client:
        ...     account = await client.get_account()
        ...     print(f"Balance: £{account.balance:.2f}")
    """

    def __init__(
        self,
        api_key: str,
        account: str,
        mpan: Optional[str] = None,
        meter_serial: Optional[str] = None,
        gas_mprn: Optional[str] = None,
        gas_meter_serial: Optional[str] = None,
    ):
        """
        Initialize the Octopus Energy client.

        Args:
            api_key: Your Octopus API key (starts with sk_live_)
            account: Your account number (e.g., A-FB05ED6C)
            mpan: Meter Point Administration Number (for electricity consumption)
            meter_serial: Electricity meter serial number
            gas_mprn: Meter Point Reference Number (for gas consumption)
            gas_meter_serial: Gas meter serial number
        """
        self.api_key = api_key
        self.account = account
        self.mpan = mpan
        self.meter_serial = meter_serial
        self.gas_mprn = gas_mprn
        self.gas_meter_serial = gas_meter_serial

        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._http: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._http = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        if self._http:
            await self._http.aclose()
            self._http = None

    async def _get_http(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http is None:
            self._http = httpx.AsyncClient()
        return self._http

    async def _get_token(self) -> str:
        """Get or refresh GraphQL authentication token."""
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token

        http = await self._get_http()
        resp = await http.post(
            GRAPHQL_URL,
            json={
                "query": """
                    mutation ObtainToken($key: String!) {
                        obtainKrakenToken(input: {APIKey: $key}) {
                            token
                        }
                    }
                """,
                "variables": {"key": self.api_key}
            }
        )
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            raise AuthenticationError(data["errors"][0]["message"])

        self._token = data["data"]["obtainKrakenToken"]["token"]
        self._token_expires = datetime.now() + timedelta(minutes=55)
        return self._token

    async def _graphql(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL query with authentication."""
        token = await self._get_token()
        http = await self._get_http()

        resp = await http.post(
            GRAPHQL_URL,
            headers={"Authorization": token},
            json={"query": query, "variables": variables or {}}
        )
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            raise APIError(data["errors"][0]["message"])

        return data["data"]

    # -------------------------------------------------------------------------
    # Account & Billing
    # -------------------------------------------------------------------------

    async def get_account(self) -> Account:
        """
        Get account information including balance.

        Returns:
            Account with balance, name, status and address
        """
        data = await self._graphql(
            """
            query GetAccount($account: String!) {
                account(accountNumber: $account) {
                    balance
                    billingName
                    status
                    properties {
                        address
                    }
                }
            }
            """,
            {"account": self.account}
        )
        acc = data["account"]
        return Account(
            number=self.account,
            balance=acc["balance"] / 100,  # pence to pounds
            name=acc["billingName"],
            status=acc["status"],
            address=acc["properties"][0]["address"] if acc["properties"] else ""
        )

    # -------------------------------------------------------------------------
    # Consumption
    # -------------------------------------------------------------------------

    async def get_consumption(
        self,
        periods: int = 48,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> list[Consumption]:
        """
        Get half-hourly electricity consumption.

        Args:
            periods: Number of 30-minute periods (default 48 = 24 hours)
            start: Start datetime (optional)
            end: End datetime (optional)

        Returns:
            List of Consumption readings
        """
        if not self.mpan or not self.meter_serial:
            raise ConfigurationError("MPAN and meter serial required for consumption data")

        http = await self._get_http()
        params = {"page_size": periods}
        if start:
            params["period_from"] = start.isoformat()
        if end:
            params["period_to"] = end.isoformat()

        resp = await http.get(
            f"{REST_API_URL}/electricity-meter-points/{self.mpan}/meters/{self.meter_serial}/consumption/",
            params=params,
            auth=(self.api_key, "")
        )
        resp.raise_for_status()
        data = resp.json()

        return [
            Consumption(
                start=datetime.fromisoformat(r["interval_start"].replace("Z", "+00:00")),
                end=datetime.fromisoformat(r["interval_end"].replace("Z", "+00:00")),
                kwh=r["consumption"]
            )
            for r in data.get("results", [])
        ]

    async def get_daily_usage(self, days: int = 7) -> dict[str, float]:
        """
        Get daily electricity consumption totals.

        Args:
            days: Number of days to fetch

        Returns:
            Dict mapping date strings to kWh totals
        """
        consumption = await self.get_consumption(periods=days * 48)
        daily: dict[str, float] = {}
        for c in consumption:
            day = c.start.strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0) + c.kwh
        return daily

    # -------------------------------------------------------------------------
    # Gas Consumption
    # -------------------------------------------------------------------------

    async def get_gas_consumption(
        self,
        periods: int = 48,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> list[GasConsumption]:
        """
        Get half-hourly gas consumption.

        Note: SMETS1 meters return kWh directly, SMETS2 meters return m³
        which is converted to kWh using a standard factor of 11.1868.

        Args:
            periods: Number of 30-minute periods (default 48 = 24 hours)
            start: Start datetime (optional)
            end: End datetime (optional)

        Returns:
            List of GasConsumption readings
        """
        if not self.gas_mprn or not self.gas_meter_serial:
            raise ConfigurationError("gas_mprn and gas_meter_serial required for gas data")

        http = await self._get_http()
        params = {"page_size": periods}
        if start:
            params["period_from"] = start.isoformat()
        if end:
            params["period_to"] = end.isoformat()

        resp = await http.get(
            f"{REST_API_URL}/gas-meter-points/{self.gas_mprn}/meters/{self.gas_meter_serial}/consumption/",
            params=params,
            auth=(self.api_key, "")
        )
        resp.raise_for_status()
        data = resp.json()

        # Standard gas conversion factor: m³ to kWh
        # (volume correction × calorific value × kWh conversion)
        M3_TO_KWH = 11.1868

        results = []
        for r in data.get("results", []):
            consumption = r["consumption"]
            # If value is small, it's likely m³ (SMETS2), convert to kWh
            # SMETS1 meters report in kWh directly (larger values)
            if consumption < 10:  # Heuristic: m³ values are typically < 10 per period
                m3 = consumption
                kwh = consumption * M3_TO_KWH
            else:
                kwh = consumption
                m3 = None

            results.append(GasConsumption(
                start=datetime.fromisoformat(r["interval_start"].replace("Z", "+00:00")),
                end=datetime.fromisoformat(r["interval_end"].replace("Z", "+00:00")),
                kwh=kwh,
                m3=m3
            ))

        return results

    async def get_daily_gas_usage(self, days: int = 7) -> dict[str, float]:
        """
        Get daily gas consumption totals in kWh.

        Args:
            days: Number of days to fetch

        Returns:
            Dict mapping date strings to kWh totals
        """
        consumption = await self.get_gas_consumption(periods=days * 48)
        daily: dict[str, float] = {}
        for c in consumption:
            day = c.start.strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0) + c.kwh
        return daily

    async def get_gas_tariff(self, region: str = "J") -> Optional[GasTariff]:
        """
        Get current gas tariff details.

        Args:
            region: DNO region code (default J = Scotland)

        Returns:
            GasTariff with rates, or None if not found
        """
        data = await self._graphql(
            """
            query GetGasTariff($account: String!) {
                account(accountNumber: $account) {
                    gasAgreements(active: true) {
                        tariff {
                            ... on StandardTariff {
                                displayName
                                productCode
                                standingCharge
                            }
                        }
                    }
                }
            }
            """,
            {"account": self.account}
        )

        agreements = data.get("account", {}).get("gasAgreements", [])
        if not agreements:
            return None

        tariff_data = agreements[0].get("tariff", {})
        product_code = tariff_data.get("productCode", "")

        # Fetch unit rate from REST API
        http = await self._get_http()
        tariff_code = f"G-1R-{product_code}-{region}"

        try:
            resp = await http.get(
                f"{REST_API_URL}/products/{product_code}/gas-tariffs/{tariff_code}/standard-unit-rates/",
                params={"page_size": 1},
                auth=(self.api_key, "")
            )
            resp.raise_for_status()
            rates_data = resp.json()
            unit_rate = rates_data.get("results", [{}])[0].get("value_inc_vat", 0)
        except httpx.HTTPError:
            unit_rate = 0

        return GasTariff(
            name=tariff_data.get("displayName", "Unknown"),
            product_code=product_code,
            standing_charge=tariff_data.get("standingCharge", 0),
            unit_rate=unit_rate
        )

    # -------------------------------------------------------------------------
    # Tariff & Rates
    # -------------------------------------------------------------------------

    async def get_tariff(self, region: str = "J") -> Optional[Tariff]:
        """
        Get current electricity tariff details.

        Args:
            region: DNO region code (default J = Scotland)

        Returns:
            Tariff with rates, or None if not found
        """
        data = await self._graphql(
            """
            query GetTariff($account: String!) {
                account(accountNumber: $account) {
                    electricityAgreements(active: true) {
                        tariff {
                            ... on HalfHourlyTariff {
                                displayName
                                productCode
                                standingCharge
                            }
                            ... on StandardTariff {
                                displayName
                                productCode
                                standingCharge
                            }
                        }
                    }
                }
            }
            """,
            {"account": self.account}
        )

        agreements = data.get("account", {}).get("electricityAgreements", [])
        if not agreements:
            return None

        tariff_data = agreements[0].get("tariff", {})
        product_code = tariff_data.get("productCode", "")

        # Fetch unit rates from REST API
        http = await self._get_http()
        tariff_code = f"E-1R-{product_code}-{region}"

        try:
            resp = await http.get(
                f"{REST_API_URL}/products/{product_code}/electricity-tariffs/{tariff_code}/standard-unit-rates/",
                params={"page_size": 10},
                auth=(self.api_key, "")
            )
            resp.raise_for_status()
            rates_data = resp.json()
        except httpx.HTTPError:
            rates_data = {"results": []}

        # Parse rates
        rates = {}
        off_peak_rate = None
        peak_rate = None

        for rate in rates_data.get("results", [])[:4]:
            val = rate.get("value_inc_vat", 0)
            if val < 15:
                off_peak_rate = val
                rates["off_peak"] = val
            else:
                peak_rate = val
                rates["peak"] = val

        return Tariff(
            name=tariff_data.get("displayName", "Unknown"),
            product_code=product_code,
            standing_charge=tariff_data.get("standingCharge", 0),
            rates=rates,
            off_peak_rate=off_peak_rate,
            peak_rate=peak_rate,
            off_peak_start="23:30",
            off_peak_end="05:30"
        )

    def get_current_rate(self, tariff: Tariff) -> Rate:
        """
        Get current rate based on time of day.

        Args:
            tariff: Tariff object with rate info

        Returns:
            Rate with current pricing and time info
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # Intelligent Octopus Go: off-peak 23:30 - 05:30
        is_off_peak = current_time >= "23:30" or current_time < "05:30"

        if is_off_peak:
            if current_time >= "23:30":
                period_end = (now + timedelta(days=1)).replace(hour=5, minute=30, second=0)
            else:
                period_end = now.replace(hour=5, minute=30, second=0)
            return Rate(
                rate=tariff.off_peak_rate or 7.0,
                is_off_peak=True,
                period_end=period_end,
                next_rate=tariff.peak_rate or 30.0
            )
        else:
            period_end = now.replace(hour=23, minute=30, second=0)
            if now >= period_end:
                period_end += timedelta(days=1)
            return Rate(
                rate=tariff.peak_rate or 30.0,
                is_off_peak=False,
                period_end=period_end,
                next_rate=tariff.off_peak_rate or 7.0
            )

    # -------------------------------------------------------------------------
    # Intelligent Octopus Dispatches
    # -------------------------------------------------------------------------

    async def get_dispatches(self) -> list[Dispatch]:
        """
        Get planned Intelligent Octopus dispatch slots.

        These are the smart charging windows scheduled by Octopus
        for your EV or battery.

        Returns:
            List of Dispatch objects
        """
        data = await self._graphql(
            """
            query GetDispatches($account: String!) {
                plannedDispatches(accountNumber: $account) {
                    start
                    end
                    delta
                }
            }
            """,
            {"account": self.account}
        )

        dispatches = []
        for d in data.get("plannedDispatches") or []:
            try:
                dispatches.append(Dispatch(
                    start=datetime.fromisoformat(d["start"].replace("Z", "+00:00")),
                    end=datetime.fromisoformat(d["end"].replace("Z", "+00:00")),
                    source="smart-charge"
                ))
            except (ValueError, KeyError):
                continue

        return sorted(dispatches, key=lambda d: d.start)

    async def get_dispatch_status(self) -> DispatchStatus:
        """
        Check if currently dispatching and get next dispatch.

        Returns:
            DispatchStatus with current state
        """
        dispatches = await self.get_dispatches()
        now = datetime.now()

        current = None
        next_dispatch = None

        for d in dispatches:
            now_tz = now.astimezone(d.start.tzinfo)
            if d.start <= now_tz <= d.end:
                current = d
            elif d.start > now_tz and next_dispatch is None:
                next_dispatch = d

        return DispatchStatus(
            is_dispatching=current is not None,
            current_dispatch=current,
            next_dispatch=next_dispatch
        )

    # -------------------------------------------------------------------------
    # Saving Sessions
    # -------------------------------------------------------------------------

    async def get_saving_sessions(self) -> list[SavingSession]:
        """
        Get upcoming Saving Sessions (free electricity events).

        Part of Octoplus - these are demand response events where
        you get rewarded for reducing consumption.

        Returns:
            List of upcoming SavingSession events
        """
        data = await self._graphql(
            """
            query GetSavingSessions($account: String!) {
                savingSessions(accountNumber: $account) {
                    events {
                        code
                        startAt
                        endAt
                        rewardPerKwhInOctoPoints
                    }
                }
            }
            """,
            {"account": self.account}
        )

        sessions = []
        now = datetime.now()

        for e in data.get("savingSessions", {}).get("events", []) or []:
            try:
                start = datetime.fromisoformat(e["startAt"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(e["endAt"].replace("Z", "+00:00"))

                # Only include upcoming or active sessions
                if end.replace(tzinfo=None) > now:
                    sessions.append(SavingSession(
                        code=e.get("code", ""),
                        start=start,
                        end=end,
                        reward_per_kwh=e.get("rewardPerKwhInOctoPoints", 0)
                    ))
            except (ValueError, KeyError):
                continue

        return sorted(sessions, key=lambda s: s.start)

    # -------------------------------------------------------------------------
    # Live Power (Home Mini)
    # -------------------------------------------------------------------------

    async def get_live_power(self, device_id: Optional[str] = None) -> Optional[LivePower]:
        """
        Get real-time power consumption from Home Mini.

        Requires a Home Mini CAD device paired with your smart meter.
        Data updates every 10-30 seconds.

        Args:
            device_id: Smart meter device ID (discovered automatically if not provided)

        Returns:
            LivePower with current demand, or None if unavailable
        """
        # If no device ID, try to discover it
        if not device_id:
            device_id = await self._discover_meter_device()
            if not device_id:
                return None

        end = datetime.now()
        start = end - timedelta(minutes=30)

        data = await self._graphql(
            """
            query GetTelemetry($deviceId: String!, $start: DateTime!, $end: DateTime!) {
                smartMeterTelemetry(
                    deviceId: $deviceId
                    grouping: HALF_HOURLY
                    start: $start
                    end: $end
                ) {
                    readAt
                    demand
                    consumption
                }
            }
            """,
            {
                "deviceId": device_id,
                "start": f"{start.isoformat()}Z",
                "end": f"{end.isoformat()}Z"
            }
        )

        telemetry = data.get("smartMeterTelemetry") or []
        if not telemetry:
            return None

        latest = telemetry[-1]
        try:
            return LivePower(
                demand_watts=int(latest.get("demand") or 0),
                read_at=datetime.fromisoformat(latest["readAt"].replace("Z", "+00:00")),
                consumption_kwh=latest.get("consumption")
            )
        except (ValueError, KeyError):
            return None

    async def _discover_meter_device(self) -> Optional[str]:
        """Discover smart meter device ID from account."""
        data = await self._graphql(
            """
            query DiscoverDevices($account: String!) {
                account(accountNumber: $account) {
                    properties {
                        electricityMeterPoints {
                            meters {
                                smartDevices {
                                    deviceId
                                }
                            }
                        }
                    }
                }
            }
            """,
            {"account": self.account}
        )

        try:
            props = data["account"]["properties"]
            for prop in props:
                for mp in prop.get("electricityMeterPoints", []):
                    for meter in mp.get("meters", []):
                        for device in meter.get("smartDevices", []):
                            if device.get("deviceId"):
                                return device["deviceId"]
        except (KeyError, TypeError):
            pass

        return None

    # -------------------------------------------------------------------------
    # Smart Devices
    # -------------------------------------------------------------------------

    async def get_smart_devices(self) -> list[SmartDevice]:
        """
        Get registered smart devices (EVs, chargers, batteries).

        Returns:
            List of SmartDevice objects
        """
        data = await self._graphql(
            """
            query GetDevices($account: String!) {
                registeredKrakenflexDevice(accountNumber: $account) {
                    krakenflexDeviceId
                    provider
                    status
                }
            }
            """,
            {"account": self.account}
        )

        device = data.get("registeredKrakenflexDevice")
        if device:
            return [SmartDevice(
                device_id=device["krakenflexDeviceId"],
                provider=device["provider"],
                status=device.get("status", "ACTIVE")
            )]
        return []


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------

class OctopusError(Exception):
    """Base exception for Open Octopus errors."""
    pass


class AuthenticationError(OctopusError):
    """Authentication failed."""
    pass


class APIError(OctopusError):
    """API request failed."""
    pass


class ConfigurationError(OctopusError):
    """Missing or invalid configuration."""
    pass
