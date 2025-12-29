#!/usr/bin/env python3
"""Claude Agent SDK integration for natural language energy queries.

Ask questions about your Octopus Energy account in plain English:
- "What's my current energy usage?"
- "When is my next charging window?"
- "How much did I use yesterday?"
- "Am I on off-peak rates right now?"

Usage:
    octopus-ask "What's my current power draw?"

Or as a library:
    from open_octopus.agent import OctopusAgent

    agent = OctopusAgent()
    response = await agent.ask("What's my balance?")
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, Any

from anthropic import Anthropic

from .client import OctopusClient
from .models import Account, Tariff, Rate, DispatchStatus, LivePower, SavingSession


# Tool definitions for Claude
OCTOPUS_TOOLS = [
    {
        "name": "get_account_info",
        "description": "Get Octopus Energy account information including balance, billing name, and status",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_current_rate",
        "description": "Get the current electricity rate, whether it's off-peak or peak, and when it changes",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_live_power",
        "description": "Get real-time power consumption from the Home Mini device in watts and calculated cost per hour",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_charging_status",
        "description": "Get Intelligent Octopus charging status - whether currently charging and when the next scheduled charge is",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_daily_usage",
        "description": "Get electricity usage for recent days in kWh",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to get usage for (default 7)",
                    "default": 7
                }
            },
            "required": []
        }
    },
    {
        "name": "get_saving_sessions",
        "description": "Get upcoming Saving Sessions (free electricity events)",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_tariff_info",
        "description": "Get electricity tariff details including name, standing charge, and unit rates",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_gas_usage",
        "description": "Get gas consumption for recent days in kWh",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to get gas usage for (default 7)",
                    "default": 7
                }
            },
            "required": []
        }
    },
    {
        "name": "get_gas_tariff",
        "description": "Get gas tariff details including name, standing charge, and unit rate",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


class OctopusAgent:
    """Claude-powered agent for natural language energy queries."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        account: Optional[str] = None,
        mpan: Optional[str] = None,
        meter_serial: Optional[str] = None,
        gas_mprn: Optional[str] = None,
        gas_meter_serial: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        """
        Initialize the Octopus Agent.

        Args:
            api_key: Octopus API key (or OCTOPUS_API_KEY env var)
            account: Account number (or OCTOPUS_ACCOUNT env var)
            mpan: MPAN (or OCTOPUS_MPAN env var)
            meter_serial: Meter serial (or OCTOPUS_METER_SERIAL env var)
            gas_mprn: Gas MPRN (or OCTOPUS_GAS_MPRN env var)
            gas_meter_serial: Gas meter serial (or OCTOPUS_GAS_METER_SERIAL env var)
            anthropic_api_key: Anthropic API key (or ANTHROPIC_API_KEY env var)
            model: Claude model to use
        """
        self.octopus = OctopusClient(
            api_key=api_key or os.environ.get("OCTOPUS_API_KEY", ""),
            account=account or os.environ.get("OCTOPUS_ACCOUNT", ""),
            mpan=mpan or os.environ.get("OCTOPUS_MPAN"),
            meter_serial=meter_serial or os.environ.get("OCTOPUS_METER_SERIAL"),
            gas_mprn=gas_mprn or os.environ.get("OCTOPUS_GAS_MPRN"),
            gas_meter_serial=gas_meter_serial or os.environ.get("OCTOPUS_GAS_METER_SERIAL")
        )

        self.anthropic = Anthropic(
            api_key=anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = model

        # Cache for fetched data
        self._cache: dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None

    async def _execute_tool(self, name: str, input_data: dict) -> dict:
        """Execute a tool and return results."""
        async with self.octopus:
            if name == "get_account_info":
                account = await self.octopus.get_account()
                return {
                    "balance": account.balance,
                    "balance_status": "credit" if account.balance < 0 else "owed",
                    "name": account.name,
                    "status": account.status,
                    "address": account.address
                }

            elif name == "get_current_rate":
                tariff = await self.octopus.get_tariff()
                if not tariff:
                    return {"error": "Could not fetch tariff information"}

                rate = self.octopus.get_current_rate(tariff)
                now = datetime.now()
                time_left = rate.period_end - now
                hours = int(time_left.total_seconds()) // 3600
                mins = (int(time_left.total_seconds()) % 3600) // 60

                return {
                    "current_rate_pence": rate.rate,
                    "is_off_peak": rate.is_off_peak,
                    "rate_type": "off-peak" if rate.is_off_peak else "peak",
                    "changes_in": f"{hours}h {mins}m",
                    "changes_at": rate.period_end.strftime("%H:%M"),
                    "next_rate_pence": rate.next_rate
                }

            elif name == "get_live_power":
                power = await self.octopus.get_live_power()
                if not power:
                    return {"error": "Live power data unavailable. Requires Home Mini device."}

                tariff = await self.octopus.get_tariff()
                rate = self.octopus.get_current_rate(tariff) if tariff else None
                cost_per_hour = (power.demand_watts / 1000 * rate.rate) if rate else 0

                return {
                    "demand_watts": power.demand_watts,
                    "demand_kw": power.demand_watts / 1000,
                    "read_at": power.read_at.isoformat(),
                    "cost_per_hour_pence": round(cost_per_hour, 1)
                }

            elif name == "get_charging_status":
                status = await self.octopus.get_dispatch_status()
                result = {
                    "is_charging": status.is_dispatching,
                }

                if status.is_dispatching and status.current_dispatch:
                    result["charging_ends"] = status.current_dispatch.end.strftime("%H:%M")

                if status.next_dispatch:
                    result["next_charge_start"] = status.next_dispatch.start.strftime("%H:%M")
                    result["next_charge_end"] = status.next_dispatch.end.strftime("%H:%M")
                    result["next_charge_duration_mins"] = status.next_dispatch.duration_minutes
                else:
                    result["next_charge"] = None

                return result

            elif name == "get_daily_usage":
                days = input_data.get("days", 7)
                daily = await self.octopus.get_daily_usage(days=days)

                return {
                    "usage_by_day": {
                        date: round(kwh, 2) for date, kwh in sorted(daily.items(), reverse=True)
                    },
                    "total_kwh": round(sum(daily.values()), 2),
                    "average_kwh": round(sum(daily.values()) / len(daily), 2) if daily else 0
                }

            elif name == "get_saving_sessions":
                sessions = await self.octopus.get_saving_sessions()

                return {
                    "sessions": [
                        {
                            "start": s.start.strftime("%Y-%m-%d %H:%M"),
                            "end": s.end.strftime("%H:%M"),
                            "is_active": s.is_active,
                            "is_upcoming": s.is_upcoming,
                            "reward_per_kwh": s.reward_per_kwh
                        }
                        for s in sessions
                    ],
                    "count": len(sessions),
                    "has_active": any(s.is_active for s in sessions)
                }

            elif name == "get_tariff_info":
                tariff = await self.octopus.get_tariff()
                if not tariff:
                    return {"error": "Could not fetch electricity tariff information"}

                return {
                    "fuel_type": "electricity",
                    "name": tariff.name,
                    "product_code": tariff.product_code,
                    "standing_charge_pence": tariff.standing_charge,
                    "off_peak_rate_pence": tariff.off_peak_rate,
                    "peak_rate_pence": tariff.peak_rate,
                    "off_peak_hours": f"{tariff.off_peak_start} - {tariff.off_peak_end}"
                }

            elif name == "get_gas_usage":
                if not self.octopus.gas_mprn:
                    return {"error": "Gas meter not configured. Set OCTOPUS_GAS_MPRN and OCTOPUS_GAS_METER_SERIAL."}

                days = input_data.get("days", 7)
                daily = await self.octopus.get_daily_gas_usage(days=days)

                return {
                    "fuel_type": "gas",
                    "usage_by_day": {
                        date: round(kwh, 2) for date, kwh in sorted(daily.items(), reverse=True)
                    },
                    "total_kwh": round(sum(daily.values()), 2),
                    "average_kwh": round(sum(daily.values()) / len(daily), 2) if daily else 0
                }

            elif name == "get_gas_tariff":
                if not self.octopus.gas_mprn:
                    return {"error": "Gas meter not configured. Set OCTOPUS_GAS_MPRN and OCTOPUS_GAS_METER_SERIAL."}

                tariff = await self.octopus.get_gas_tariff()
                if not tariff:
                    return {"error": "Could not fetch gas tariff information"}

                return {
                    "fuel_type": "gas",
                    "name": tariff.name,
                    "product_code": tariff.product_code,
                    "standing_charge_pence": tariff.standing_charge,
                    "unit_rate_pence": tariff.unit_rate
                }

            else:
                return {"error": f"Unknown tool: {name}"}

    async def ask(self, question: str) -> str:
        """
        Ask a natural language question about your energy data.

        Args:
            question: Plain English question about energy usage, rates, etc.

        Returns:
            Natural language response from Claude
        """
        system_prompt = """You are an expert assistant for Octopus Energy customers in the UK.
You help users understand their energy usage, billing, and smart tariff features.

Key context:
- Intelligent Octopus Go has off-peak rates from 23:30 to 05:30 (6 hours of cheap electricity)
- Home Mini is a device that shows real-time power consumption
- Saving Sessions are events where customers get rewarded for reducing usage
- Balance shown as negative means the customer has credit

When answering:
- Be concise and friendly
- Use the tools to get current data before answering
- Convert pence to pounds where appropriate (e.g., 30p = £0.30)
- Format times in 12-hour format for readability when natural
- If data isn't available, explain what's needed (e.g., Home Mini for live power)
"""

        messages = [{"role": "user", "content": question}]

        # Initial request with tools
        response = self.anthropic.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            tools=OCTOPUS_TOOLS,
            messages=messages
        )

        # Process tool calls iteratively
        while response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    result = await self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # Continue conversation with tool results
            messages = [
                {"role": "user", "content": question},
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results}
            ]

            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                tools=OCTOPUS_TOOLS,
                messages=messages
            )

        # Extract final text response
        for block in response.content:
            if hasattr(block, 'text'):
                return block.text

        return "I couldn't generate a response. Please try again."


async def ask(question: str) -> str:
    """Convenience function to ask a question."""
    agent = OctopusAgent()
    return await agent.ask(question)


def main():
    """CLI entry point for octopus-ask."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: octopus-ask \"Your question about energy\"")
        print("\nExamples:")
        print('  octopus-ask "What\'s my current power usage?"')
        print('  octopus-ask "When is my next charging window?"')
        print('  octopus-ask "How much did I use yesterday?"')
        print('  octopus-ask "Am I on off-peak rates?"')
        sys.exit(1)

    question = " ".join(sys.argv[1:])

    try:
        response = asyncio.run(ask(question))
        print(response)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
