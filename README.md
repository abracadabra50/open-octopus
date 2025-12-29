<div align="center">

# 🐙 open-octopus

### The Octopus Energy API, done right.

<br />

**Smart meters. Live power. Intelligent charging.**
**All the features Octopus buried in GraphQL.**

<br />

[![PyPI version](https://img.shields.io/pypi/v/open-octopus.svg?style=for-the-badge&color=7C3AED)](https://pypi.org/project/open-octopus/)
[![Python](https://img.shields.io/badge/python-3.10+-7C3AED.svg?style=for-the-badge)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge)](LICENSE)

<br />

```bash
pip install open-octopus
```

**Async. Typed. Batteries included.**

<br />

[Features](#features) · [Quick Start](#quick-start) · [CLI](#-cli) · [AI Agent](#-ai-agent) · [API Reference](#-api-reference)

</div>

<br />

---

<br />

## Features

<table>
<tr>
<td width="50%">

### ⚡ Live Power

**Real-time consumption from Home Mini.**

See exactly what you're using right now. Updates every 10-30 seconds. Calculate cost per hour at current rates.

</td>
<td width="50%">

### 🔌 Smart Charging

**Intelligent Octopus dispatch slots.**

Know when your EV is charging. See upcoming charge windows. Never miss off-peak rates again.

</td>
</tr>
<tr>
<td width="50%">

### 🎁 Saving Sessions

**Free electricity events.**

Get notified about upcoming free power events. Track rewards in Octopoints. Never miss free energy.

</td>
<td width="50%">

### 🔥 Dual Fuel

**Electricity + gas support.**

Track both meters. Get consumption history. See tariff details for gas and electric.

</td>
</tr>
<tr>
<td width="50%">

### 🤖 AI Agent

**Ask questions in plain English.**

"What's my current rate?" "How much did I use yesterday?" Powered by Claude.

</td>
<td width="50%">

### 🖥️ Menu Bar

**macOS status bar app.**

Live power, current rate, charging status, and balance. Always visible. One click away.

</td>
</tr>
</table>

<br />

---

<br />

## Quick Start

<table>
<tr>
<td>

### ⚡ Basic Usage

```python
import asyncio
from open_octopus import OctopusClient

async def main():
    async with OctopusClient(
        api_key="sk_live_xxx",
        account="A-XXXXXXXX"
    ) as client:
        # Account balance
        account = await client.get_account()
        print(f"Balance: £{account.balance:.2f}")

        # Current rate
        tariff = await client.get_tariff()
        rate = client.get_current_rate(tariff)
        print(f"Rate: {rate.rate}p/kWh")

        # Live power (Home Mini)
        power = await client.get_live_power()
        if power:
            print(f"Power: {power.demand_kw:.2f} kW")

asyncio.run(main())
```

</td>
<td>

### 🔥 With Gas

```python
async with OctopusClient(
    api_key="sk_live_xxx",
    account="A-XXXXXXXX",
    gas_mprn="1234567890",
    gas_meter_serial="G4A12345"
) as client:
    # Gas consumption
    gas = await client.get_daily_gas_usage(days=7)
    for date, kwh in gas.items():
        print(f"{date}: {kwh:.1f} kWh")

    # Gas tariff
    tariff = await client.get_gas_tariff()
    print(f"Rate: {tariff.unit_rate}p/kWh")
```

</td>
</tr>
</table>

<br />

---

<br />

## 💻 CLI

```bash
octopus status      # Full overview
octopus rate        # Current rate (off-peak/peak)
octopus power       # Live consumption
octopus dispatch    # Charging windows
octopus usage       # Electricity usage
octopus gas         # Gas usage
octopus sessions    # Saving sessions
octopus watch       # Live monitoring
```

<br />

---

<br />

## 🤖 AI Agent

**Ask questions about your energy in plain English.**

```bash
pip install 'open-octopus[agent]'
export ANTHROPIC_API_KEY="sk-ant-xxx"

octopus-ask "What's my current rate?"
octopus-ask "How much gas did I use this week?"
octopus-ask "When is my next charging window?"
octopus-ask "Am I on off-peak rates right now?"
```

<br />

Or use in Python:

```python
from open_octopus import OctopusAgent

agent = OctopusAgent()
response = await agent.ask("What's my balance?")
print(response)
```

<br />

---

<br />

## 🖥️ Menu Bar (macOS)

```bash
pip install 'open-octopus[menubar]'
octopus-menubar
```

<table>
<tr>
<td align="center">⚡<br/><b>Live Power</b><br/><sub>Real-time kW</sub></td>
<td align="center">🌙<br/><b>Rate Status</b><br/><sub>Off-peak/peak</sub></td>
<td align="center">🔌<br/><b>Charging</b><br/><sub>EV dispatch</sub></td>
<td align="center">💰<br/><b>Balance</b><br/><sub>Account credit</sub></td>
</tr>
</table>

<br />

---

<br />

## 📚 API Reference

<table>
<tr>
<td width="50%">

**Account & Billing**
```python
get_account()           # Balance, status, address
get_tariff()            # Electricity tariff
get_gas_tariff()        # Gas tariff
get_current_rate()      # Current rate + off-peak
```

</td>
<td width="50%">

**Consumption**
```python
get_consumption()       # Half-hourly readings
get_daily_usage()       # Daily totals
get_gas_consumption()   # Gas readings
get_daily_gas_usage()   # Daily gas totals
```

</td>
</tr>
<tr>
<td width="50%">

**Smart Features**
```python
get_live_power()        # Real-time watts
get_dispatches()        # Charge windows
get_dispatch_status()   # Currently charging?
get_saving_sessions()   # Free power events
```

</td>
<td width="50%">

**Models**
```python
Account                 # Balance, name, status
Tariff / GasTariff      # Rates, standing charge
Rate                    # Current rate, period
Dispatch                # Charge window
LivePower               # Real-time demand
SavingSession           # Free power event
```

</td>
</tr>
</table>

<br />

---

<br />

## ⚙️ Configuration

<details>
<summary><b>Environment Variables</b></summary>

```bash
# Required
OCTOPUS_API_KEY=sk_live_xxx
OCTOPUS_ACCOUNT=A-XXXXXXXX

# Electricity meter (optional)
OCTOPUS_MPAN=1234567890123
OCTOPUS_METER_SERIAL=12A3456789

# Gas meter (optional)
OCTOPUS_GAS_MPRN=1234567890
OCTOPUS_GAS_METER_SERIAL=G4A12345

# AI agent (optional)
ANTHROPIC_API_KEY=sk-ant-xxx
```

</details>

<details>
<summary><b>Getting Your API Key</b></summary>

1. Log in to [Octopus Energy](https://octopus.energy/dashboard/)
2. Go to **Developer Settings**
3. Copy your API key (starts with `sk_live_`)

</details>

<details>
<summary><b>Finding Your MPAN/MPRN</b></summary>

Your MPAN (electricity) and MPRN (gas) are on your energy bills.

Or discover them via the API:
```python
account = await client.get_account()
print(account)  # Includes meter info
```

</details>

<br />

---

<br />

## How It Works

```
┌────────────────────────────────────────────────────────────────┐
│  Octopus Energy GraphQL API (Kraken)                           │
│  ↓                                                             │
│  open-octopus async client                                     │
│  • Account balance, tariffs                                    │
│  • Consumption data (electricity + gas)                        │
│  • Intelligent Octopus dispatches                              │
│  • Live power (Home Mini telemetry)                            │
│  • Saving Sessions                                             │
│  ↓                                                             │
│  Your choice of interface                                      │
│  • Python library (async/await)                                │
│  • CLI tool (octopus)                                          │
│  • AI agent (octopus-ask)                                      │
│  • Menu bar app (octopus-menubar)                              │
└────────────────────────────────────────────────────────────────┘
```

<br />

---

<br />

<div align="center">

**Built for Octopus Energy customers** 🐙

[Report Bug](https://github.com/abracadabra50/open-octopus/issues) · [Request Feature](https://github.com/abracadabra50/open-octopus/issues)

<br />

MIT License · [Octopus Energy](https://octopus.energy) · [GraphQL API](https://developer.octopus.energy/graphql/)

</div>
