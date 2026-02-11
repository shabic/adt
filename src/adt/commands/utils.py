"""Utility commands (registered as top-level)."""
import re
import sys
import click
from rich.console import Console
from ..core import DeviceManager, ADBError

console = Console()


@click.command()
@click.option('-d', '--device', help='Device serial number')
def ip(device):
    """Show device IP address.

    Gets the IP address of the Android device (wlan0 interface).
    """
    try:
        adb = DeviceManager.get_adb(device)

        # Try to get IP from wlan0
        ifconfig_output = adb.shell("ifconfig wlan0", check=False)

        # Check if command failed (empty output or starts with error message)
        if not ifconfig_output or ifconfig_output.startswith("ifconfig:") or ifconfig_output.startswith("error:"):
            console.print("[yellow]Warning:[/yellow] Could not get wlan0 info")
            console.print("Trying ip addr")
            # Try alternative command
            ip_output = adb.shell("ip addr show wlan0", check=False)
            if ip_output:
                # Parse ip addr output
                match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_output)
                if match:
                    console.print(match.group(1))
                    return
            console.print("[red]Error:[/red] Could not determine device IP")
            sys.exit(1)

        # Parse ifconfig output
        # Look for "inet addr:xxx.xxx.xxx.xxx" or "inet xxx.xxx.xxx.xxx"
        match = re.search(r'inet addr:(\d+\.\d+\.\d+\.\d+)', ifconfig_output)
        if not match:
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ifconfig_output)

        if match:
            console.print(match.group(1))
        else:
            console.print("[red]Error:[/red] Could not parse IP address")
            sys.exit(1)

    except ADBError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@click.command()
@click.argument('key', required=False)
@click.option('-d', '--device', help='Device serial number')
def getprop(key, device):
    """Get system property.

    If KEY is not provided, lists all properties.
    """
    try:
        adb = DeviceManager.get_adb(device)

        if key:
            # Validate property key: only allow alphanumeric, dots, underscores, hyphens
            if not re.match(r'^[a-zA-Z0-9._\-]+$', key):
                console.print(f"[red]Error:[/red] Invalid property key: {key}")
                sys.exit(1)
            # Get specific property
            output = adb.shell(f"getprop {key}")
            console.print(output)
        else:
            # Get all properties and format them
            output = adb.shell("getprop")

            # Format output: [key]: [value] -> key=value
            lines = output.strip().split('\n')
            for line in lines:
                # Remove brackets and format
                formatted = line.replace(']: [', '=').replace('[', '').replace(']', '')
                console.print(formatted)

    except ADBError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@click.command()
@click.argument('command', required=True)
@click.option('-d', '--device', help='Device serial number')
def su(command, device):
    """Execute command as root.

    Runs the specified command with root privileges using su.
    Output streams in real-time (suitable for long-running commands like tcpdump).
    """
    try:
        adb = DeviceManager.get_adb(device)
        rc = adb.shell_interactive(command, root=True)
        if rc and rc != 130:
            sys.exit(rc)

    except ADBError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def get_commands():
    """Return all utility commands as (name, command) tuples."""
    return [
        ('ip', ip),
        ('getprop', getprop),
        ('su', su),
    ]
