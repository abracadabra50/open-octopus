# 🐙 Open Octopus

> **Unofficial** open-source macOS menu bar app for [Octopus Energy](https://octopus.energy) customers.
> Not affiliated with or endorsed by Octopus Energy.

![Open Octopus Menu Bar App](docs/menubar-screenshot.png)

## Features

- **Live Rate Display** - Current electricity rate with countdown to off-peak
- **Smart Charging** - EV dispatch status with golden indicator when charging
- **Usage Insights** - Today/yesterday consumption with sparkline visualization
- **Rate Comparison** - Peak vs off-peak rates with savings percentage
- **Monthly Projection** - Estimated monthly cost based on recent usage
- **AI Assistant** - Ask questions about your energy usage (powered by Claude)
- **Quick Actions** - One-click common queries

## Installation

### Requirements
- macOS 14.0+
- Python 3.10+
- Octopus Energy account with API key

### Setup

1. **Install the Python package:**
   ```bash
   pip install open-octopus
   ```

2. **Set your credentials:**
   ```bash
   export OCTOPUS_API_KEY="your_api_key"
   export OCTOPUS_ACCOUNT="A-XXXXXXXX"
   export OCTOPUS_MPAN="your_mpan"           # Optional: for consumption data
   export OCTOPUS_METER_SERIAL="your_serial" # Optional: for consumption data
   ```

3. **Build and run the macOS app:**
   ```bash
   git clone https://github.com/abracadabra50/open-octopus.git
   cd open-octopus
   xcodebuild -workspace OctopusMenuBar.xcworkspace -scheme OctopusMenuBar build
   open ~/Library/Developer/Xcode/DerivedData/OctopusMenuBar-*/Build/Products/Debug/OctopusMenuBar.app
   ```

## CLI Tools

Open Octopus also includes command-line tools:

```bash
# Check current rate
octopus rate

# View account balance
octopus account

# Get live power (if available)
octopus power

# View consumption
octopus usage

# Check dispatch status (Intelligent Octopus)
octopus dispatch

# AI assistant
octopus-ask "What's the best time to run my dishwasher?"
```

## Configuration

Create `~/.octopus.env` for persistent configuration:

```bash
OCTOPUS_API_KEY=sk_live_xxxxx
OCTOPUS_ACCOUNT=A-XXXXXXXX
OCTOPUS_MPAN=1234567890123
OCTOPUS_METER_SERIAL=12A3456789
ANTHROPIC_API_KEY=sk-ant-xxxxx  # For AI features
```

## Supported Tariffs

- Intelligent Octopus Go
- Octopus Go
- Agile Octopus
- Flexible Octopus
- And more...

## License

MIT

## Credits

Built with SwiftUI and Python. AI powered by [Claude](https://anthropic.com).
