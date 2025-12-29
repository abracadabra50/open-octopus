#!/usr/bin/env python3
"""JSON server for SwiftUI menu bar app.

Communicates with Swift app via stdin/stdout JSON.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Any

from .client import OctopusClient
from .models import Tariff

# Optional agent import
try:
    from .agent import OctopusAgent
    HAS_AGENT = True
except ImportError:
    HAS_AGENT = False


class MenuBarServer:
    """JSON server for menu bar app communication."""

    def __init__(self):
        # Credentials from environment
        self.api_key = os.environ.get("OCTOPUS_API_KEY", "")
        self.account = os.environ.get("OCTOPUS_ACCOUNT", "")
        self.mpan = os.environ.get("OCTOPUS_MPAN")
        self.meter_serial = os.environ.get("OCTOPUS_METER_SERIAL")
        self.gas_mprn = os.environ.get("OCTOPUS_GAS_MPRN")
        self.gas_meter_serial = os.environ.get("OCTOPUS_GAS_METER_SERIAL")

        if not self.api_key or not self.account:
            self._output_error("Missing OCTOPUS_API_KEY or OCTOPUS_ACCOUNT")
            sys.exit(1)

        self.client = OctopusClient(
            api_key=self.api_key,
            account=self.account,
            mpan=self.mpan,
            meter_serial=self.meter_serial
        )

    def _output(self, data: dict):
        """Output JSON to stdout (for Swift to read)."""
        print(json.dumps(data), flush=True)

    def _output_error(self, message: str):
        """Output error JSON."""
        self._output({"error": message})

    async def fetch_data(self) -> dict[str, Any]:
        """Fetch all data from Octopus API."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "live_power_watts": None,
            "rate": None,
            "is_off_peak": False,
            "rate_ends_in_seconds": 0,
            "balance": 0.0,
            "balance_is_credit": False,
            "dispatch_status": "none",  # none, charging, scheduled
            "dispatch_end": None,
            "next_dispatch_start": None,
            "next_dispatch_end": None,
            "yesterday_kwh": 0.0,
            "yesterday_cost": 0.0,
            "today_kwh": 0.0,
            "today_cost": 0.0,
            "hourly_usage": [],  # Last 24h
            "live_history": [],  # Last hour of live readings
            "tariff_name": None,
            "standing_charge": 0.0,
            "has_saving_session": False,
            "saving_session_start": None,
            "saving_session_end": None,
            "saving_session_active": False,
            # New computed fields for 10x UI
            "off_peak_start": "23:30",
            "off_peak_end": "05:30",
            "off_peak_percentage": 0.0,
            "monthly_projection": 0.0,
            "peak_rate": None,
            "off_peak_rate": None,
            "charger_provider": None,  # e.g., "HYPERVOLT", "OHME", "TESLA"
            "charge_history": [],  # Recent charge sessions [{start, end, kwh, duration_mins}]
        }

        try:
            async with self.client:
                # Account balance from API: negative = you owe, positive = credit
                account = await self.client.get_account()
                result["balance"] = abs(account.balance)
                result["balance_is_credit"] = account.balance > 0  # True only if credit

                # Tariff and current rate
                tariff = await self.client.get_tariff()
                if tariff:
                    result["tariff_name"] = tariff.product_code
                    result["standing_charge"] = tariff.standing_charge
                    result["peak_rate"] = tariff.peak_rate
                    result["off_peak_rate"] = tariff.off_peak_rate

                    rate_info = self.client.get_current_rate(tariff)
                    result["rate"] = rate_info.rate
                    result["is_off_peak"] = rate_info.is_off_peak

                    now = datetime.now()
                    time_left = rate_info.period_end - now
                    result["rate_ends_in_seconds"] = max(0, int(time_left.total_seconds()))

                # Dispatch status
                dispatch = await self.client.get_dispatch_status()
                if dispatch:
                    if dispatch.is_dispatching:
                        result["dispatch_status"] = "charging"
                        if dispatch.current_dispatch:
                            result["dispatch_end"] = dispatch.current_dispatch.end.isoformat()
                    elif dispatch.next_dispatch:
                        result["dispatch_status"] = "scheduled"
                        result["next_dispatch_start"] = dispatch.next_dispatch.start.isoformat()
                        result["next_dispatch_end"] = dispatch.next_dispatch.end.isoformat()

                # Get charger/EV provider (e.g., HYPERVOLT, OHME, TESLA)
                devices = await self.client.get_smart_devices()
                if devices:
                    result["charger_provider"] = devices[0].provider

                # Get completed charge sessions history
                completed = await self.client.get_completed_dispatches(limit=5)
                charge_history = []
                # Use off-peak rate for cost calculation (charging happens at off-peak)
                off_peak_rate = result.get("off_peak_rate") or 7.0
                for session in completed:
                    duration = int((session["end"] - session["start"]).total_seconds() / 60)
                    kwh = round(session["kwh"], 2)
                    cost = round(kwh * off_peak_rate / 100, 2)  # Convert pence to pounds
                    charge_history.append({
                        "start": session["start"].isoformat(),
                        "end": session["end"].isoformat(),
                        "kwh": kwh,
                        "duration_mins": duration,
                        "cost": cost
                    })
                result["charge_history"] = charge_history

                # Live power
                live_power = await self.client.get_live_power()
                if live_power:
                    result["live_power_watts"] = live_power.demand_watts

                # Saving sessions
                sessions = await self.client.get_saving_sessions()
                if sessions:
                    session = sessions[0]
                    result["has_saving_session"] = True
                    result["saving_session_start"] = session.start.isoformat()
                    result["saving_session_end"] = session.end.isoformat()
                    result["saving_session_active"] = session.is_active

                # Consumption data
                if self.mpan and self.meter_serial:
                    consumption = await self.client.get_consumption(periods=96)

                    daily = defaultdict(float)
                    hourly_by_day = defaultdict(lambda: defaultdict(float))
                    # Half-hourly: slot 0 = 00:00, slot 1 = 00:30, slot 47 = 23:30
                    half_hourly_by_day = defaultdict(lambda: defaultdict(float))

                    for c in consumption:
                        day = c.start.strftime("%Y-%m-%d")
                        hour = c.start.hour
                        minute = c.start.minute
                        slot = hour * 2 + (1 if minute >= 30 else 0)  # 0-47
                        daily[day] += c.kwh
                        hourly_by_day[day][hour] += c.kwh
                        half_hourly_by_day[day][slot] = c.kwh

                    sorted_days = sorted(daily.keys(), reverse=True)

                    # Smart meter data has delay - use most recent available days
                    today = datetime.now().strftime("%Y-%m-%d")
                    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                    # Use actual available data for display
                    latest_day = sorted_days[0] if sorted_days else None
                    prev_day = sorted_days[1] if len(sorted_days) > 1 else None

                    # For "today" display, use most recent day with data
                    display_today = latest_day if latest_day else today
                    display_yesterday = prev_day if prev_day else yesterday

                    # Include actual data dates so UI can show them
                    result["data_date_latest"] = display_today
                    result["data_date_previous"] = display_yesterday

                    if display_today in daily:
                        result["today_kwh"] = daily[display_today]
                        result["today_cost"] = self._calculate_cost(
                            daily[display_today], hourly_by_day[display_today], tariff
                        )

                    if display_yesterday in daily:
                        result["yesterday_kwh"] = daily[display_yesterday]
                        result["yesterday_cost"] = self._calculate_cost(
                            daily[display_yesterday], hourly_by_day[display_yesterday], tariff
                        )

                    # Build hourly usage from most recent 24h of available data
                    hourly = []
                    if display_yesterday in hourly_by_day:
                        for h in range(24):
                            hourly.append(hourly_by_day[display_yesterday].get(h, 0))
                    if display_today in hourly_by_day:
                        for h in range(24):
                            hourly.append(hourly_by_day[display_today].get(h, 0))
                    # Take last 24 entries
                    result["hourly_usage"] = hourly[-24:] if hourly else []

                    # Build half-hourly usage from most recent 48 slots
                    half_hourly = []
                    if display_yesterday in half_hourly_by_day:
                        for s in range(48):
                            half_hourly.append(half_hourly_by_day[display_yesterday].get(s, 0))
                    if display_today in half_hourly_by_day:
                        for s in range(48):
                            half_hourly.append(half_hourly_by_day[display_today].get(s, 0))
                    # Take last 48 entries (24 hours of half-hourly data)
                    result["half_hourly_usage"] = half_hourly[-48:] if half_hourly else []

                    # Calculate off-peak percentage for most recent day
                    if display_today in hourly_by_day and result["today_kwh"] > 0:
                        # Off-peak hours: 0-5 and 23 (23:30-05:30)
                        off_peak_kwh = sum(
                            hourly_by_day[display_today].get(h, 0) for h in list(range(6)) + [23]
                        )
                        result["off_peak_percentage"] = round(
                            (off_peak_kwh / result["today_kwh"]) * 100, 1
                        )

                    # Calculate monthly projection from yesterday's cost
                    if result["yesterday_cost"] > 0:
                        result["monthly_projection"] = round(result["yesterday_cost"] * 30, 2)
                    elif result["today_cost"] > 0:
                        result["monthly_projection"] = round(result["today_cost"] * 30, 2)

        except Exception as e:
            result["error"] = str(e)

        return result

    def _calculate_cost(
        self,
        total_kwh: float,
        hourly: dict[int, float],
        tariff: Optional[Tariff]
    ) -> float:
        """Calculate cost for a day's usage."""
        if not tariff:
            return total_kwh * 0.245  # Default estimate

        # Estimate off-peak hours (typically 23:30-05:30 for Intelligent Octopus)
        off_peak_kwh = sum(hourly.get(h, 0) for h in range(6)) + hourly.get(23, 0)
        peak_kwh = total_kwh - off_peak_kwh

        off_rate = tariff.off_peak_rate or 7.0
        peak_rate = tariff.peak_rate or 30.0

        cost = (off_peak_kwh * off_rate + peak_kwh * peak_rate) / 100
        cost += tariff.standing_charge / 100

        return cost

    def _base_response(self) -> dict[str, Any]:
        """Return base response structure with all required fields."""
        return {
            "timestamp": datetime.now().isoformat(),
            "live_power_watts": None,
            "rate": None,
            "is_off_peak": False,
            "rate_ends_in_seconds": 0,
            "balance": 0.0,
            "balance_is_credit": False,
            "dispatch_status": "none",
            "dispatch_end": None,
            "next_dispatch_start": None,
            "next_dispatch_end": None,
            "yesterday_kwh": 0.0,
            "yesterday_cost": 0.0,
            "today_kwh": 0.0,
            "today_cost": 0.0,
            "hourly_usage": [],
            "live_history": [],
            "tariff_name": None,
            "standing_charge": 0.0,
            "has_saving_session": False,
            "saving_session_start": None,
            "saving_session_end": None,
            "saving_session_active": False,
            "off_peak_start": "23:30",
            "off_peak_end": "05:30",
            "off_peak_percentage": 0.0,
            "monthly_projection": 0.0,
            "peak_rate": None,
            "off_peak_rate": None,
            "charger_provider": None,
            "charge_history": [],
            "half_hourly_usage": [],
        }

    async def handle_ask(self, question: str) -> dict[str, Any]:
        """Handle AI question."""
        result = self._base_response()

        if not HAS_AGENT:
            result["error"] = "Agent not installed. Run: pip install 'open-octopus[agent]'"
            return result

        try:
            agent = OctopusAgent(
                api_key=self.api_key,
                account=self.account,
                mpan=self.mpan,
                meter_serial=self.meter_serial,
                gas_mprn=self.gas_mprn,
                gas_meter_serial=self.gas_meter_serial
            )
            response = await agent.ask(question)
            result["response"] = response
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    async def run(self):
        """Main run loop - read commands from stdin, output to stdout."""
        # Output initial data
        data = await self.fetch_data()
        self._output(data)

        # Read commands from stdin
        loop = asyncio.get_event_loop()

        while True:
            try:
                # Read line from stdin (non-blocking)
                line = await loop.run_in_executor(None, sys.stdin.readline)

                if not line:
                    # EOF - Swift app closed
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    cmd = json.loads(line)
                except json.JSONDecodeError:
                    self._output_error(f"Invalid JSON: {line}")
                    continue

                command = cmd.get("command", "")

                if command == "refresh":
                    data = await self.fetch_data()
                    self._output(data)

                elif command == "ask":
                    question = cmd.get("question", "")
                    if question:
                        result = await self.handle_ask(question)
                        self._output(result)
                    else:
                        self._output_error("Missing question")

                elif command == "quit":
                    break

                else:
                    self._output_error(f"Unknown command: {command}")

            except Exception as e:
                self._output_error(str(e))


def main():
    """Entry point for menu bar server."""
    server = MenuBarServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
