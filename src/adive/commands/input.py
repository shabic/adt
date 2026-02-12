"""Input commands."""
import sys
import click
from rich.console import Console
from ..core import DeviceManager, ADBError

console = Console()


@click.command('input-text')
@click.argument('text', required=True)
@click.option('-d', '--device', help='Device serial number')
def input_text(text, device):
    """Send text input to device.

    TEXT is the text to send. Spaces and special characters are supported.
    """
    try:
        adb = DeviceManager.get_adb(device)

        # Escape single quotes in text to prevent injection
        escaped_text = text.replace("'", "'\"'\"'")
        # Send text input
        adb.shell(f"input text '{escaped_text}'")
        console.print(f"[green]✓[/green] Sent text: {text}")

    except ADBError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
