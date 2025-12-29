"""Command-line interface for Open Octopus."""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .client import OctopusClient, OctopusError

app = typer.Typer(
    name="octopus",
    help="Open Octopus - CLI for Octopus Energy API",
    no_args_is_help=True
)
console = Console()


def get_client() -> OctopusClient:
    """Create client from environment variables."""
    api_key = os.environ.get("OCTOPUS_API_KEY")
    account = os.environ.get("OCTOPUS_ACCOUNT")
    mpan = os.environ.get("OCTOPUS_MPAN")
    meter_serial = os.environ.get("OCTOPUS_METER_SERIAL")

    if not api_key or not account:
        console.print("[red]Error:[/] OCTOPUS_API_KEY and OCTOPUS_ACCOUNT must be set")
        console.print("\nSet environment variables:")
        console.print("  export OCTOPUS_API_KEY='sk_live_xxx'")
        console.print("  export OCTOPUS_ACCOUNT='A-XXXXXXXX'")
        raise typer.Exit(1)

    return OctopusClient(api_key, account, mpan, meter_serial)


def run_async(coro):
    """Run an async function."""
    return asyncio.run(coro)


# -----------------------------------------------------------------------------
# Commands
# -----------------------------------------------------------------------------

@app.command()
def account():
    """Show account balance and info."""
    async def _run():
        async with get_client() as client:
            acc = await client.get_account()

            balance_color = "green" if acc.balance < 0 else "yellow"
            balance_text = f"£{abs(acc.balance):.2f} {'credit' if acc.balance < 0 else 'owed'}"

            console.print(Panel(
                f"[bold]{acc.name}[/]\n"
                f"Account: {acc.number}\n"
                f"Status: {acc.status}\n"
                f"Balance: [{balance_color}]{balance_text}[/]\n"
                f"Address: {acc.address}",
                title="Octopus Energy Account"
            ))

    run_async(_run())


@app.command()
def rate():
    """Show current electricity rate."""
    async def _run():
        async with get_client() as client:
            tariff = await client.get_tariff()
            if not tariff:
                console.print("[red]Could not fetch tariff info[/]")
                return

            current = client.get_current_rate(tariff)
            time_left = current.period_end - datetime.now()
            hours = int(time_left.total_seconds()) // 3600
            mins = (int(time_left.total_seconds()) % 3600) // 60

            if current.is_off_peak:
                console.print(f"[green]🌙 OFF-PEAK[/] [bold]{current.rate:.1f}p/kWh[/]")
                console.print(f"   Ends in {hours}h {mins}m (at 05:30)")
            else:
                console.print(f"[yellow]☀️ PEAK[/] [bold]{current.rate:.1f}p/kWh[/]")
                console.print(f"   Cheap rate in {hours}h {mins}m (at 23:30)")

            console.print(f"\n[dim]Tariff: {tariff.name}[/]")
            console.print(f"[dim]Standing charge: {tariff.standing_charge:.1f}p/day[/]")

    run_async(_run())


@app.command()
def dispatch():
    """Show Intelligent Octopus dispatch status."""
    async def _run():
        async with get_client() as client:
            status = await client.get_dispatch_status()

            if status.is_dispatching and status.current_dispatch:
                d = status.current_dispatch
                console.print(f"[green bold]⚡ CHARGING NOW[/]")
                console.print(f"   Until {d.end.strftime('%H:%M')}")
            elif status.next_dispatch:
                d = status.next_dispatch
                now = datetime.now().astimezone(d.start.tzinfo)
                delta = d.start - now
                hours = int(delta.total_seconds()) // 3600
                mins = (int(delta.total_seconds()) % 3600) // 60
                console.print(f"[blue]🔌 Next charge:[/] {d.start.strftime('%H:%M')} - {d.end.strftime('%H:%M')}")
                console.print(f"   In {hours}h {mins}m ({d.duration_minutes}min window)")
            else:
                console.print("[dim]🔌 No dispatches scheduled[/]")

            # Show all upcoming dispatches
            dispatches = await client.get_dispatches()
            if len(dispatches) > 1:
                console.print("\n[bold]Upcoming dispatches:[/]")
                for d in dispatches[:5]:
                    console.print(f"  • {d.start.strftime('%a %H:%M')} - {d.end.strftime('%H:%M')}")

    run_async(_run())


@app.command()
def power():
    """Show live power consumption (requires Home Mini)."""
    async def _run():
        async with get_client() as client:
            live = await client.get_live_power()

            if live:
                watts = live.demand_watts
                if watts >= 1000:
                    power_str = f"{watts/1000:.2f} kW"
                else:
                    power_str = f"{watts} W"

                console.print(f"[bold]⚡ {power_str}[/]")
                console.print(f"[dim]   Read at {live.read_at.strftime('%H:%M:%S')}[/]")

                # Estimate hourly cost
                tariff = await client.get_tariff()
                if tariff:
                    current = client.get_current_rate(tariff)
                    cost_per_hour = (watts / 1000) * current.rate
                    console.print(f"   ~{cost_per_hour:.1f}p/hour at current rate")
            else:
                console.print("[yellow]No live power data available[/]")
                console.print("[dim]This requires a Home Mini paired with your smart meter.[/]")

    run_async(_run())


@app.command()
def sessions():
    """Show upcoming Saving Sessions (free electricity)."""
    async def _run():
        async with get_client() as client:
            sessions = await client.get_saving_sessions()

            if not sessions:
                console.print("[dim]No upcoming Saving Sessions[/]")
                return

            console.print("[bold]🎁 Saving Sessions[/]\n")
            for s in sessions:
                if s.is_active:
                    console.print(f"[green bold]⚡ ACTIVE NOW[/] until {s.end.strftime('%H:%M')}")
                else:
                    console.print(f"📅 {s.start.strftime('%a %d %b %H:%M')} - {s.end.strftime('%H:%M')}")
                console.print(f"   [dim]{s.reward_per_kwh} Octopoints per kWh saved[/]")

    run_async(_run())


@app.command()
def usage(days: int = typer.Option(7, "--days", "-d", help="Number of days")):
    """Show daily electricity usage."""
    async def _run():
        async with get_client() as client:
            try:
                daily = await client.get_daily_usage(days)
            except Exception as e:
                console.print(f"[red]Error:[/] {e}")
                console.print("[dim]Note: MPAN and meter serial required for consumption data[/]")
                return

            if not daily:
                console.print("[dim]No consumption data available[/]")
                return

            table = Table(title=f"Last {days} Days Usage")
            table.add_column("Date", style="cyan")
            table.add_column("kWh", justify="right")
            table.add_column("Graph", justify="left")

            max_kwh = max(daily.values()) if daily else 1
            for date, kwh in sorted(daily.items(), reverse=True):
                bars = int((kwh / max_kwh) * 20)
                bar_str = "█" * bars
                table.add_row(date, f"{kwh:.1f}", f"[green]{bar_str}[/]")

            console.print(table)

    run_async(_run())


@app.command()
def status():
    """Show complete status overview."""
    async def _run():
        async with get_client() as client:
            console.print("[bold]🐙 Octopus Energy Status[/]\n")

            # Account
            try:
                acc = await client.get_account()
                balance_text = f"£{abs(acc.balance):.2f} {'credit' if acc.balance < 0 else 'owed'}"
                console.print(f"💰 Balance: [bold]{balance_text}[/]")
            except OctopusError as e:
                console.print(f"[red]Account error: {e}[/]")

            # Rate
            try:
                tariff = await client.get_tariff()
                if tariff:
                    current = client.get_current_rate(tariff)
                    rate_icon = "🌙" if current.is_off_peak else "☀️"
                    console.print(f"{rate_icon} Rate: [bold]{current.rate:.1f}p/kWh[/]")
            except OctopusError:
                pass

            # Live power
            try:
                live = await client.get_live_power()
                if live:
                    power_str = f"{live.demand_kw:.2f}kW" if live.demand_watts >= 1000 else f"{live.demand_watts}W"
                    console.print(f"⚡ Power: [bold]{power_str}[/]")
            except OctopusError:
                pass

            # Dispatch
            try:
                status = await client.get_dispatch_status()
                if status.is_dispatching:
                    console.print(f"🔌 [green]CHARGING[/]")
                elif status.next_dispatch:
                    console.print(f"🔌 Next: {status.next_dispatch.start.strftime('%H:%M')}")
            except OctopusError:
                pass

            # Sessions
            try:
                sessions = await client.get_saving_sessions()
                if sessions:
                    s = sessions[0]
                    if s.is_active:
                        console.print(f"🎁 [green bold]FREE POWER[/] until {s.end.strftime('%H:%M')}")
                    else:
                        console.print(f"🎁 Session: {s.start.strftime('%a %H:%M')}")
            except OctopusError:
                pass

    run_async(_run())


@app.command()
def watch(interval: int = typer.Option(30, "--interval", "-i", help="Refresh interval in seconds")):
    """Watch live power consumption (Ctrl+C to stop)."""
    async def _run():
        from rich.live import Live

        client = get_client()
        async with client:
            with Live(console=console, refresh_per_second=1) as live:
                while True:
                    try:
                        power = await client.get_live_power()
                        tariff = await client.get_tariff()

                        if power and tariff:
                            watts = power.demand_watts
                            current = client.get_current_rate(tariff)
                            cost_per_hour = (watts / 1000) * current.rate

                            if watts >= 1000:
                                power_str = f"{watts/1000:.2f} kW"
                            else:
                                power_str = f"{watts} W"

                            rate_icon = "🌙" if current.is_off_peak else "☀️"
                            text = Text()
                            text.append(f"⚡ {power_str}", style="bold")
                            text.append(f" │ {rate_icon} {current.rate:.1f}p", style="dim")
                            text.append(f" │ ~{cost_per_hour:.0f}p/hr", style="dim")
                            live.update(Panel(text, title=f"Live Power ({power.read_at.strftime('%H:%M:%S')})"))
                        else:
                            live.update(Panel("[dim]Waiting for data...[/]"))

                        await asyncio.sleep(interval)
                    except KeyboardInterrupt:
                        break

    try:
        run_async(_run())
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped[/]")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
