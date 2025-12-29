#!/usr/bin/env python3
"""Octopus Energy Mac Menu Bar App.

Live energy monitoring in your menu bar using open-octopus library.

Usage:
    octopus-menubar

Or run directly:
    python -m open_octopus.menubar
"""

import os
import asyncio
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

try:
    import rumps
except ImportError:
    rumps = None

from .client import OctopusClient
from .models import Tariff, DispatchStatus, SavingSession, LivePower


class OctopusMenuBar(rumps.App):
    """Octopus Energy menu bar app - real-time energy monitoring."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        account: Optional[str] = None,
        mpan: Optional[str] = None,
        meter_serial: Optional[str] = None,
    ):
        super().__init__(
            "⚡ --",
            title="⚡ --",
            quit_button=None
        )

        # Get credentials from args or environment
        self.api_key = api_key or os.environ.get("OCTOPUS_API_KEY", "")
        self.account_number = account or os.environ.get("OCTOPUS_ACCOUNT", "")
        self.mpan = mpan or os.environ.get("OCTOPUS_MPAN")
        self.meter_serial = meter_serial or os.environ.get("OCTOPUS_METER_SERIAL")

        if not self.api_key or not self.account_number:
            raise ValueError(
                "Missing credentials. Set OCTOPUS_API_KEY and OCTOPUS_ACCOUNT "
                "environment variables or pass to constructor."
            )

        # Create client
        self.client = OctopusClient(
            api_key=self.api_key,
            account=self.account_number,
            mpan=self.mpan,
            meter_serial=self.meter_serial
        )

        # State
        self.tariff: Optional[Tariff] = None
        self.dispatch: Optional[DispatchStatus] = None
        self.saving_sessions: list[SavingSession] = []
        self.live_power: Optional[LivePower] = None
        self.balance = 0.0
        self.latest_kwh = 0.0
        self.latest_cost = 0.0
        self.latest_day = ""
        self.last_refresh: Optional[datetime] = None

        # Build menu
        self._build_menu()

        # Timers
        self.title_timer = rumps.Timer(self._update_title, 1)
        self.title_timer.start()

        self.refresh_timer = rumps.Timer(self._refresh_timer, 30)
        self.refresh_timer.start()

        # Initial data fetch
        self._refresh_async()

    def _build_menu(self):
        """Build the menu structure."""
        self.live_item = rumps.MenuItem("")
        self.dispatch_item = rumps.MenuItem("🔌 Loading...")
        self.rate_item = rumps.MenuItem("Loading...")
        self.session_item = rumps.MenuItem("")
        self.balance_item = rumps.MenuItem("Loading...")
        self.usage_item = rumps.MenuItem("Loading...")
        self.status_item = rumps.MenuItem("")

        self.menu = [
            self.live_item,
            self.dispatch_item,
            self.rate_item,
            self.session_item,
            None,
            self.balance_item,
            self.usage_item,
            None,
            self.status_item,
            rumps.MenuItem("Refresh", callback=self._refresh_clicked),
            rumps.MenuItem("Open Dashboard", callback=self._open_dashboard),
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

        # Hide optional items initially
        self.live_item.hidden = True
        self.session_item.hidden = True

    def _update_title(self, _):
        """Update menu bar title every second."""
        parts = []

        if self.tariff:
            now = datetime.now()
            rate_info = self.client.get_current_rate(self.tariff)
            rate = rate_info.rate
            is_off_peak = rate_info.is_off_peak
            rate_icon = "🌙" if is_off_peak else "☀️"

            # Live power
            if self.live_power:
                watts = self.live_power.demand_watts
                power_str = f"{watts/1000:.1f}kW" if watts >= 1000 else f"{watts}W"
                parts.append(f"⚡{power_str}")
                cost_per_hour = (watts / 1000) * rate
                self.live_item.title = f"⚡ LIVE: {power_str} ({cost_per_hour:.0f}p/hr)"
                self.live_item.hidden = False
            else:
                self.live_item.hidden = True

            # Dispatch status
            if self.dispatch and self.dispatch.is_dispatching:
                parts.append("🔌CHG")
                if self.dispatch.current_dispatch:
                    end_time = self.dispatch.current_dispatch.end.strftime("%H:%M")
                    self.dispatch_item.title = f"⚡ CHARGING until {end_time}"
                else:
                    self.dispatch_item.title = "⚡ CHARGING NOW"
            elif self.dispatch and self.dispatch.next_dispatch:
                try:
                    d = self.dispatch.next_dispatch
                    now_tz = now.astimezone(d.start.tzinfo)
                    delta = d.start - now_tz
                    total_secs = int(delta.total_seconds())
                    if total_secs > 0:
                        hours = total_secs // 3600
                        mins = (total_secs % 3600) // 60
                        self.dispatch_item.title = f"🔌 Charging in {hours}h {mins}m ({d.start.strftime('%H:%M')}-{d.end.strftime('%H:%M')})"
                    else:
                        self.dispatch_item.title = "🔌 No scheduled charge"
                except Exception:
                    self.dispatch_item.title = "🔌 No scheduled charge"
            else:
                self.dispatch_item.title = "🔌 No scheduled charge"

            # Rate countdown
            time_left = rate_info.period_end - now
            hours = int(time_left.total_seconds()) // 3600
            mins = (int(time_left.total_seconds()) % 3600) // 60

            if is_off_peak:
                self.rate_item.title = f"🌙 OFF-PEAK {rate:.1f}p │ ends in {hours}h {mins}m"
            else:
                self.rate_item.title = f"☀️ PEAK {rate:.1f}p │ cheap in {hours}h {mins}m"

            parts.append(f"{rate_icon}{rate:.0f}p")

            # Saving sessions
            if self.saving_sessions:
                session = self.saving_sessions[0]
                if session.is_active:
                    self.session_item.title = f"🎁 FREE POWER until {session.end.strftime('%H:%M')}!"
                    self.session_item.hidden = False
                    parts.insert(0, "🎁FREE")
                elif session.is_upcoming:
                    self.session_item.title = f"🎁 Free power {session.start.strftime('%H:%M')}-{session.end.strftime('%H:%M')}"
                    self.session_item.hidden = False
                else:
                    self.session_item.hidden = True
            else:
                self.session_item.hidden = True

        # Build title
        if parts:
            self.title = " │ ".join(parts)
        else:
            self.title = "⚡ Loading..."

        # Update status
        if self.last_refresh:
            ago = int((datetime.now() - self.last_refresh).total_seconds())
            self.status_item.title = f"📡 Updated {ago}s ago"

    def _refresh_timer(self, _):
        """Timer callback for API refresh."""
        self._refresh_async()

    def _refresh_clicked(self, _):
        """Manual refresh button clicked."""
        self._refresh_async()

    def _open_dashboard(self, _):
        """Open Octopus dashboard in browser."""
        import subprocess
        subprocess.run(["open", "https://octopus.energy/dashboard/"])

    def _refresh_async(self):
        """Refresh data in background thread."""
        thread = threading.Thread(target=self._run_refresh)
        thread.daemon = True
        thread.start()

    def _run_refresh(self):
        """Run the async refresh in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._refresh())
        except Exception as e:
            print(f"Refresh error: {e}")
        finally:
            loop.close()

    async def _refresh(self):
        """Fetch data from Octopus API."""
        try:
            async with self.client:
                # Account balance
                account = await self.client.get_account()
                self.balance = account.balance

                # Tariff and rates
                self.tariff = await self.client.get_tariff()

                # Dispatch status
                self.dispatch = await self.client.get_dispatch_status()

                # Saving sessions
                self.saving_sessions = await self.client.get_saving_sessions()

                # Live power (Home Mini)
                self.live_power = await self.client.get_live_power()

                # Consumption data
                if self.mpan and self.meter_serial:
                    consumption = await self.client.get_consumption(periods=96)
                    daily = defaultdict(float)
                    hourly_by_day = defaultdict(lambda: defaultdict(float))

                    for c in consumption:
                        day = c.start.strftime("%Y-%m-%d")
                        hour = c.start.hour
                        daily[day] += c.kwh
                        hourly_by_day[day][hour] += c.kwh

                    sorted_days = sorted(daily.keys(), reverse=True)
                    self.latest_day = sorted_days[0] if sorted_days else ""
                    self.latest_kwh = daily.get(self.latest_day, 0)

                    # Calculate cost
                    if self.tariff and self.latest_day:
                        hourly = hourly_by_day[self.latest_day]
                        off_peak_kwh = sum(hourly.get(h, 0) for h in range(6)) + hourly.get(23, 0)
                        peak_kwh = self.latest_kwh - off_peak_kwh
                        off_rate = self.tariff.off_peak_rate or 7.0
                        peak_rate = self.tariff.peak_rate or 30.0
                        self.latest_cost = (
                            (off_peak_kwh * off_rate + peak_kwh * peak_rate) / 100
                            + self.tariff.standing_charge / 100
                        )
                    else:
                        self.latest_cost = self.latest_kwh * 0.245

            self.last_refresh = datetime.now()
            self._update_menu()

        except Exception as e:
            print(f"API error: {e}")

    def _update_menu(self):
        """Update menu items after refresh."""
        # Balance
        if self.balance < 0:
            self.balance_item.title = f"💰 £{abs(self.balance):.2f} credit"
        else:
            self.balance_item.title = f"💰 £{self.balance:.2f} owed"

        # Latest day usage
        if self.latest_day:
            date = datetime.strptime(self.latest_day, "%Y-%m-%d")
            today = datetime.now().date()
            if date.date() == today:
                label = "Today"
            elif date.date() == today - timedelta(days=1):
                label = "Yesterday"
            else:
                label = date.strftime("%a %d")
            self.usage_item.title = f"📈 {label}: {self.latest_kwh:.1f} kWh │ £{self.latest_cost:.2f}"


def main():
    """Run the Octopus Energy menu bar app."""
    if rumps is None:
        print("Error: rumps is required for the menu bar app.")
        print("Install with: pip install 'open-octopus[menubar]'")
        return 1

    try:
        app = OctopusMenuBar()
        app.run()
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    main()
