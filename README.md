# Open Octopus 🐙

Modern async Python client for the **Octopus Energy GraphQL API**.

Supports features not available in the REST API:
- ⚡ **Live power consumption** (requires Home Mini)
- 🔌 **Intelligent Octopus dispatch slots**
- 🎁 **Saving Sessions** / Free Electricity events
- 💰 **Account balance** and tariff info
- 🖥️ **macOS menu bar app** for live monitoring
- 🤖 **Claude AI agent** for natural language queries

## Installation

```bash
# Core library
pip install open-octopus

# With macOS menu bar app
pip install 'open-octopus[menubar]'

# With Claude AI agent
pip install 'open-octopus[agent]'

# Everything
pip install 'open-octopus[all]'
```

## Quick Start

```python
import asyncio
from open_octopus import OctopusClient

async def main():
    async with OctopusClient(
        api_key="sk_live_xxx",
        account="A-XXXXXXXX"
    ) as client:
        # Get account balance
        account = await client.get_account()
        print(f"Balance: £{account.balance:.2f}")

        # Get current rate
        tariff = await client.get_tariff()
        rate = client.get_current_rate(tariff)
        print(f"Rate: {rate.rate}p/kWh ({'off-peak' if rate.is_off_peak else 'peak'})")

        # Get live power (requires Home Mini)
        power = await client.get_live_power()
        if power:
            print(f"Current draw: {power.demand_kw:.2f} kW")

asyncio.run(main())
```

## CLI Usage

```bash
# Set environment variables
export OCTOPUS_API_KEY="sk_live_xxx"
export OCTOPUS_ACCOUNT="A-XXXXXXXX"
export OCTOPUS_MPAN="1234567890123"  # Optional, for consumption data
export OCTOPUS_METER_SERIAL="12A3456789"  # Optional

# Show account info
octopus account

# Show current rate
octopus rate

# Show dispatch status (Intelligent Octopus)
octopus dispatch

# Show live power consumption
octopus power

# Show upcoming saving sessions
octopus sessions

# Show daily usage
octopus usage --days 7

# Full status overview
octopus status

# Watch live power (updates every 30s)
octopus watch
```

## Features

### Account & Billing

```python
account = await client.get_account()
print(f"Name: {account.name}")
print(f"Balance: £{account.balance:.2f}")
print(f"Status: {account.status}")
```

### Tariff & Rates

```python
tariff = await client.get_tariff()
print(f"Tariff: {tariff.name}")
print(f"Standing charge: {tariff.standing_charge}p/day")

# Get current rate with time-of-use info
rate = client.get_current_rate(tariff)
print(f"Current: {rate.rate}p/kWh")
print(f"Off-peak: {rate.is_off_peak}")
print(f"Changes at: {rate.period_end}")
```

### Consumption Data

```python
# Get last 48 half-hourly readings
consumption = await client.get_consumption(periods=48)
for c in consumption:
    print(f"{c.start}: {c.kwh:.3f} kWh")

# Get daily totals
daily = await client.get_daily_usage(days=7)
for date, kwh in daily.items():
    print(f"{date}: {kwh:.1f} kWh")
```

### Intelligent Octopus Dispatches

```python
# Check if currently charging
status = await client.get_dispatch_status()
if status.is_dispatching:
    print(f"Charging until {status.current_dispatch.end}")
elif status.next_dispatch:
    print(f"Next charge: {status.next_dispatch.start}")

# Get all scheduled dispatches
dispatches = await client.get_dispatches()
for d in dispatches:
    print(f"{d.start} - {d.end} ({d.duration_minutes}min)")
```

### Saving Sessions

```python
sessions = await client.get_saving_sessions()
for s in sessions:
    if s.is_active:
        print(f"FREE POWER until {s.end}!")
    else:
        print(f"Upcoming: {s.start} - {s.end}")
        print(f"  Reward: {s.reward_per_kwh} Octopoints/kWh")
```

### Live Power (Home Mini)

Requires a [Home Mini](https://octopus.energy/blog/home-mini/) paired with your smart meter.

```python
power = await client.get_live_power()
if power:
    print(f"Demand: {power.demand_watts}W")
    print(f"Read at: {power.read_at}")

    # Calculate cost per hour
    tariff = await client.get_tariff()
    rate = client.get_current_rate(tariff)
    cost_per_hour = (power.demand_watts / 1000) * rate.rate
    print(f"Cost: {cost_per_hour:.1f}p/hour")
```

## macOS Menu Bar App

Live energy monitoring in your menu bar:

```bash
# Install with menubar support
pip install 'open-octopus[menubar]'

# Run
octopus-menubar
```

Shows:
- ⚡ Live power consumption (with Home Mini)
- 🌙/☀️ Current rate (off-peak/peak)
- 🔌 Charging status (Intelligent Octopus)
- 🎁 Saving Sessions alerts
- 💰 Account balance

## Claude AI Agent

Ask questions about your energy in plain English:

```bash
# Install with agent support
pip install 'open-octopus[agent]'

# Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-xxx"

# Ask questions
octopus-ask "What's my current power usage?"
octopus-ask "When is my next charging window?"
octopus-ask "How much did I use yesterday?"
octopus-ask "Am I on off-peak rates right now?"
```

Or use in Python:

```python
from open_octopus import OctopusAgent
import asyncio

async def main():
    agent = OctopusAgent()
    response = await agent.ask("What's my current rate?")
    print(response)

asyncio.run(main())
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OCTOPUS_API_KEY` | Yes | API key from Octopus dashboard |
| `OCTOPUS_ACCOUNT` | Yes | Account number (e.g., A-FB05ED6C) |
| `OCTOPUS_MPAN` | No | Meter Point Admin Number (for consumption) |
| `OCTOPUS_METER_SERIAL` | No | Electricity meter serial number |
| `ANTHROPIC_API_KEY` | For agent | Anthropic API key (for octopus-ask) |

### Getting Your API Key

1. Log in to [Octopus Energy](https://octopus.energy/dashboard/)
2. Go to **Developer Settings**
3. Copy your API key (starts with `sk_live_`)

### Finding Your MPAN

Your MPAN is on your electricity bill, or run:

```python
# The API can discover your meter points
account = await client.get_account()
print(account)  # Includes property info
```

## Comparison with Other Libraries

| Feature | open-octopus | octopus-energy | Home Assistant |
|---------|--------------|----------------|----------------|
| REST API | ✅ | ✅ | ✅ |
| GraphQL API | ✅ | ❌ | ✅ |
| Live power (Home Mini) | ✅ | ❌ | ✅ |
| Intelligent dispatches | ✅ | ❌ | ✅ |
| Saving sessions | ✅ | ❌ | ✅ |
| Account balance | ✅ | ❌ | ✅ |
| Standalone library | ✅ | ✅ | ❌ |
| CLI tool | ✅ | ❌ | ❌ |
| Async/await | ✅ | ✅ | ❌ |
| Typed models | ✅ | ❌ | ❌ |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## Links

- [Octopus Energy Developer API](https://developer.octopus.energy/)
- [GraphQL API Documentation](https://developer.octopus.energy/graphql/)
- [Report Issues](https://github.com/abracadabra50/open-octopus/issues)
