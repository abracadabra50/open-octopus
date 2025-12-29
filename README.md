# Open Octopus 🐙

Modern async Python client for the **Octopus Energy API**.

```bash
pip install open-octopus
```

## Features

- ⚡ **Live power** - Real-time consumption (Home Mini)
- 🔌 **Smart charging** - Intelligent Octopus dispatch slots
- 🎁 **Saving Sessions** - Free electricity events
- 🔥 **Dual fuel** - Electricity + gas support
- 🤖 **AI agent** - Natural language queries
- 🖥️ **Menu bar** - macOS status bar app

## Quick Start

```python
import asyncio
from open_octopus import OctopusClient

async def main():
    async with OctopusClient(
        api_key="sk_live_xxx",
        account="A-XXXXXXXX"
    ) as client:
        # Account
        account = await client.get_account()
        print(f"Balance: £{account.balance:.2f}")

        # Current rate
        tariff = await client.get_tariff()
        rate = client.get_current_rate(tariff)
        print(f"Rate: {rate.rate}p ({'off-peak' if rate.is_off_peak else 'peak'})")

        # Live power (requires Home Mini)
        power = await client.get_live_power()
        if power:
            print(f"Power: {power.demand_kw:.2f} kW")

asyncio.run(main())
```

## Environment Variables

```bash
# Required
export OCTOPUS_API_KEY="sk_live_xxx"
export OCTOPUS_ACCOUNT="A-XXXXXXXX"

# Electricity meter (optional)
export OCTOPUS_MPAN="1234567890123"
export OCTOPUS_METER_SERIAL="12A3456789"

# Gas meter (optional)
export OCTOPUS_GAS_MPRN="1234567890"
export OCTOPUS_GAS_METER_SERIAL="G4A12345"

# AI agent (optional)
export ANTHROPIC_API_KEY="sk-ant-xxx"
```

## CLI

```bash
octopus status      # Full overview
octopus rate        # Current rate
octopus power       # Live consumption
octopus dispatch    # Charging status
octopus usage       # Daily usage
octopus gas         # Gas usage
```

## AI Agent

Ask questions in plain English:

```bash
pip install 'open-octopus[agent]'

octopus-ask "What's my current rate?"
octopus-ask "How much gas did I use yesterday?"
octopus-ask "When is my next charging window?"
```

## Gas Support

```python
async with OctopusClient(
    api_key="sk_live_xxx",
    account="A-XXXXXXXX",
    gas_mprn="1234567890",
    gas_meter_serial="G4A12345"
) as client:
    # Gas consumption
    gas = await client.get_gas_consumption(periods=48)
    for reading in gas:
        print(f"{reading.start}: {reading.kwh:.2f} kWh")

    # Gas tariff
    tariff = await client.get_gas_tariff()
    print(f"Rate: {tariff.unit_rate}p/kWh")

    # Daily gas usage
    daily = await client.get_daily_gas_usage(days=7)
    for date, kwh in daily.items():
        print(f"{date}: {kwh:.1f} kWh")
```

## Menu Bar (macOS)

```bash
pip install 'open-octopus[menubar]'
octopus-menubar
```

Shows live power, current rate, charging status, and balance.

## API Reference

### Client Methods

| Method | Description |
|--------|-------------|
| `get_account()` | Account info and balance |
| `get_tariff()` | Electricity tariff details |
| `get_current_rate(tariff)` | Current rate with off-peak status |
| `get_consumption()` | Half-hourly electricity readings |
| `get_daily_usage()` | Daily electricity totals |
| `get_live_power()` | Real-time power (Home Mini) |
| `get_dispatches()` | Intelligent Octopus charge slots |
| `get_dispatch_status()` | Current charging status |
| `get_saving_sessions()` | Free electricity events |
| `get_gas_consumption()` | Half-hourly gas readings |
| `get_daily_gas_usage()` | Daily gas totals |
| `get_gas_tariff()` | Gas tariff details |

## License

MIT
