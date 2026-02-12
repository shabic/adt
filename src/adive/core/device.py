"""Device manager for handling device selection."""
from typing import Optional, Tuple
import sys
import click
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt
from .adb import ADB, ADBError
from .utils import is_piped

console = Console()
console_stderr = Console(stderr=True)


class DeviceManager:
    """Manager for device selection and validation."""

    @staticmethod
    def _get_device_info(device_id: str) -> Tuple[str, str]:
        """Get device manufacturer and model.

        Args:
            device_id: Device serial number

        Returns:
            Tuple of (manufacturer, model)
        """
        try:
            adb = ADB(device_id)

            # Get manufacturer
            manufacturer = adb.shell("getprop ro.product.manufacturer", check=False).strip()
            if not manufacturer:
                manufacturer = adb.shell("getprop ro.product.brand", check=False).strip()

            # Get model
            model = adb.shell("getprop ro.product.model", check=False).strip()

            # Fallback if empty
            if not manufacturer:
                manufacturer = "Unknown"
            if not model:
                model = "Unknown"

            return manufacturer, model
        except Exception as e:
            # Log the error for debugging but don't crash
            console_stderr.print(f"[dim]Warning: Could not get device info: {e}[/dim]")
            return "Unknown", "Unknown"

    @staticmethod
    def select_device(device_id: Optional[str] = None) -> str:
        """Select device interactively if multiple devices are connected.

        Args:
            device_id: Optional device ID. If provided, validates it exists.

        Returns:
            Selected device ID

        Raises:
            ADBError: If no devices found or invalid device ID
        """
        devices = ADB.list_devices()

        if not devices:
            raise ADBError(
                "No devices found. Please connect a device and ensure USB debugging is enabled."
            )

        # Filter out unauthorized devices
        authorized_devices = [(dev_id, status) for dev_id, status in devices if status == "device"]

        if not authorized_devices:
            unauthorized = [dev_id for dev_id, status in devices if status == "unauthorized"]
            if unauthorized:
                raise ADBError(
                    f"Device(s) found but unauthorized: {', '.join(unauthorized)}\n"
                    "Please authorize USB debugging on your device."
                )
            else:
                raise ADBError("No authorized devices found.")

        # If device_id provided, validate it
        if device_id:
            if device_id not in [dev_id for dev_id, _ in authorized_devices]:
                raise ADBError(f"Device '{device_id}' not found or not authorized.")
            return device_id

        # If only one device, use it
        if len(authorized_devices) == 1:
            return authorized_devices[0][0]

        # Check if output is piped - if so, auto-select first device
        if is_piped():
            selected = authorized_devices[0][0]
            console_stderr.print(f"[dim]Auto-selecting first device ({selected}) - output is piped[/dim]")
            return selected

        # Multiple devices - prompt user to select
        console_stderr.print("\n[bold cyan]Multiple devices found:[/bold cyan]")

        # Get device info for all devices
        console_stderr.print("[dim]Fetching device info...[/dim]")
        device_info = []
        for dev_id, status in authorized_devices:
            manufacturer, model = DeviceManager._get_device_info(dev_id)
            device_info.append((dev_id, status, manufacturer, model))

        # Create a nice table
        table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Device ID", style="green")
        table.add_column("Manufacturer", style="blue")
        table.add_column("Model", style="blue")
        table.add_column("Status", style="yellow")

        for idx, (dev_id, status, manufacturer, model) in enumerate(device_info, 1):
            table.add_row(str(idx), dev_id, manufacturer, model, status)

        console_stderr.print(table)

        while True:
            try:
                choice = IntPrompt.ask(
                    "[bold cyan]Select device[/bold cyan]",
                    default=1,
                    console=console_stderr
                )
                if 1 <= choice <= len(authorized_devices):
                    selected = authorized_devices[choice - 1][0]
                    console_stderr.print(f"[green]✓[/green] Selected: [bold]{selected}[/bold]\n")
                    return selected
                else:
                    console_stderr.print(f"[red]✗[/red] Invalid choice. Please enter 1-{len(authorized_devices)}")
            except (ValueError, KeyboardInterrupt):
                console_stderr.print("\n[yellow]Device selection cancelled[/yellow]")
                raise ADBError("Device selection cancelled.")

    @staticmethod
    def get_adb(device_id: Optional[str] = None) -> ADB:
        """Get ADB instance with device selection.

        Args:
            device_id: Optional device ID

        Returns:
            ADB instance configured for selected device
        """
        selected_device = DeviceManager.select_device(device_id)
        return ADB(selected_device)
