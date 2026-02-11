"""App management commands."""
import sys
import click
import os
import re
from rich.console import Console
from rich.table import Table
from ..core import DeviceManager, PackageResolver, ADBError, resolve_uid, escape_shell_arg

console = Console()


@click.group()
def app():
    """App management commands."""
    pass


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
def info(package, device):
    """Show comprehensive app information.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        console.print(f"[bold cyan]App Information:[/bold cyan] {pkg}\n")

        # Get PID
        pid_output = adb.shell(f"pidof {pkg}", check=False)
        pid = pid_output.strip() if pid_output else "Not running"

        # Get UID
        uid = "Unknown"
        try:
            dumpsys_output = adb.shell(f"dumpsys package {pkg}")
            uid_match = re.search(r'uid=(\d+)', dumpsys_output)
            if uid_match:
                uid = uid_match.group(1)
        except Exception:
            pass

        # Get version
        version = "Unknown"
        try:
            version = resolver.get_version(pkg)
        except Exception:
            pass

        # Get path
        path = "Unknown"
        try:
            path_output = adb.shell(f"pm path {pkg}")
            if path_output:
                path = path_output.split(':', 1)[1].strip() if ':' in path_output else path_output
        except Exception:
            pass

        # Get architecture
        arch = "Unknown"
        if path != "Unknown" and "base.apk" in path:
            try:
                lib_path = path.replace("base.apk", "lib/")
                arch_output = adb.shell(f"ls {lib_path}", check=False)
                if arch_output and not arch_output.startswith("ls:"):
                    arch = arch_output.strip()
            except Exception:
                pass

        # Display info
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Package", pkg)
        table.add_row("Version", version)
        table.add_row("PID", pid)
        table.add_row("UID", uid)
        table.add_row("Architecture", arch)
        table.add_row("Path", path)

        console.print(table)

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
def kill(package, device):
    """Force stop an app.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        adb.shell(f"am force-stop {pkg}")
        console.print(f"[green]✓[/green] Force stopped: {pkg}")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
def path(package, device):
    """Get app base APK path.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        path_output = adb.shell(f"pm path {pkg}")
        if path_output:
            # Take only the first line (base.apk)
            first_line = path_output.strip().split('\n')[0]
            path = first_line.split(':', 1)[1].strip() if ':' in first_line else first_line
            console.print(path)
        else:
            console.print(f"[red]Error:[/red] Could not get path for {pkg}")
            sys.exit(1)

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-o', '--output', help='Output filename (default: <package>-<version>.apk)')
def pull(package, device, output):
    """Pull base APK from device.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        # Get path (only first line for base.apk)
        path_output = adb.shell(f"pm path {pkg}")
        if not path_output:
            console.print(f"[red]Error:[/red] Could not get path for {pkg}")
            sys.exit(1)

        # Take only the first line (base.apk)
        first_line = path_output.strip().split('\n')[0]
        apk_path = first_line.split(':', 1)[1].strip() if ':' in first_line else first_line

        # Get version if output not specified
        if not output:
            version = resolver.get_version(pkg)
            output = f"{pkg}-{version}.apk"

        console.print(f"Pulling APK from {apk_path}")
        adb.pull(apk_path, output)
        console.print(f"[green]✓[/green] Saved to: {output}")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command('pull-all')
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-o', '--output-dir', help='Output directory (default: <version>)')
def pull_all(package, device, output_dir):
    """Pull all APKs (including splits) from device.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        # Get all paths
        paths_output = adb.shell(f"pm path {pkg}")
        if not paths_output:
            console.print(f"[red]Error:[/red] Could not get paths for {pkg}")
            sys.exit(1)

        paths = []
        for line in paths_output.strip().split('\n'):
            if line.startswith('package:'):
                paths.append(line.split(':', 1)[1].strip())

        # Get version for directory name
        if not output_dir:
            version = resolver.get_version(pkg)
            output_dir = version

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        console.print(f"Pulling {len(paths)} APK(s) to {output_dir}/")
        for apk_path in paths:
            filename = os.path.basename(apk_path)
            local_path = os.path.join(output_dir, filename)
            console.print(f"  Pulling {filename}")
            adb.pull(apk_path, local_path)

        console.print(f"[green]✓[/green] Pulled {len(paths)} APK(s) to: {output_dir}/")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-y', '--yes', is_flag=True, help='Skip confirmation')
def clean(package, device, yes):
    """Clear app data.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        if not yes:
            console.print(f"[bold yellow]Clear all data for [red]{pkg}[/red]?[/bold yellow]")
            click.confirm("Proceed?", abort=True)

        adb.shell(f"pm clear {pkg}")
        console.print(f"[green]✓[/green] Cleared data for: {pkg}")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-y', '--yes', is_flag=True, help='Skip confirmation')
def uninstall(package, device, yes):
    """Uninstall app from device.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        if not yes:
            console.print(f"[bold yellow]Uninstall [red]{pkg}[/red]?[/bold yellow]")
            click.confirm("Proceed?", abort=True)

        adb.uninstall(pkg)
        console.print(f"[green]✓[/green] Uninstalled: {pkg}")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
def libs(package, device):
    """List native libraries for an app.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        # Get path
        path_output = adb.shell(f"pm path {pkg}")
        if not path_output:
            console.print(f"[red]Error:[/red] Could not get path for {pkg}")
            sys.exit(1)

        apk_path = path_output.split(':', 1)[1].strip() if ':' in path_output else path_output

        if "base.apk" not in apk_path:
            console.print(f"[yellow]Warning:[/yellow] Not a standard app path: {apk_path}")
            sys.exit(1)

        lib_base = apk_path.replace("base.apk", "lib/")

        # Get architecture
        arch_output = adb.shell(f"ls {lib_base}", check=False)
        if not arch_output or arch_output.startswith("ls:"):
            console.print(f"[yellow]No native libraries found[/yellow]")
            return

        arch = arch_output.strip()
        lib_path = apk_path.replace("base.apk", f"lib/{arch}/")

        # List libraries
        libs_output = adb.shell(f"ls -la {lib_path}", check=False)
        if libs_output and not libs_output.startswith("ls:"):
            console.print(f"[bold cyan]Native libraries ({arch}):[/bold cyan]\n")
            # Skip first 3 lines (total, ., ..)
            lines = libs_output.strip().split('\n')[3:]
            for line in lines:
                console.print(line)
        else:
            console.print(f"[yellow]No libraries found in {lib_path}[/yellow]")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
def ps(package, device):
    """Show app processes.

    If PACKAGE is not provided, uses the current foreground app.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        uid = resolve_uid(adb, pkg)
        if not uid:
            console.print(f"[yellow]No processes found for {pkg}[/yellow]")
            return

        # Get all processes with this UID using word-boundary match
        escaped_uid = escape_shell_arg(uid)
        all_ps_output = adb.shell(f"ps -A | grep -wF '{escaped_uid}'")
        console.print(f"[bold cyan]Processes for {pkg}:[/bold cyan]\n")
        console.print(all_ps_output)

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command('install-multiple')
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True), required=False, default='.')
@click.option('-d', '--device', help='Device serial number')
@click.option('-r', '--replace', is_flag=True, help='Replace existing application')
def install_multiple(directory, device, replace):
    """Install split APKs from a directory.

    Installs base.apk and all split_*.apk files from the specified directory.
    This is useful for installing apps with split APKs (Android App Bundles).

    DIRECTORY: Path to directory containing base.apk and split APKs (default: current directory)
    """
    try:
        adb = DeviceManager.get_adb(device)

        # Use absolute path
        directory = os.path.abspath(directory)

        # Find all APK files
        apk_files = []
        base_apk = None

        for filename in os.listdir(directory):
            if filename.endswith('.apk'):
                filepath = os.path.join(directory, filename)
                if filename == 'base.apk':
                    base_apk = filepath
                    apk_files.insert(0, filepath)  # base.apk should be first
                elif filename.startswith('split_'):
                    apk_files.append(filepath)

        if not apk_files:
            console.print(f"[red]Error:[/red] No APK files found in {directory}")
            sys.exit(1)

        if not base_apk:
            console.print(f"[yellow]Warning:[/yellow] base.apk not found, installing available APKs")

        console.print(f"[bold cyan]Found {len(apk_files)} APK(s) to install:[/bold cyan]")
        for apk in apk_files:
            console.print(f"  - {os.path.basename(apk)}")

        # Build install-multiple command
        cmd = ["install-multiple"]
        if replace:
            cmd.append("-r")

        # Add all APK paths
        cmd.extend(apk_files)

        console.print(f"\n[bold cyan]Installing {len(apk_files)} APK(s)...[/bold cyan]")

        # Execute install-multiple
        stdout, stderr, returncode = adb.execute(cmd, check=False)

        if returncode == 0:
            console.print(f"[green]✓[/green] Successfully installed {len(apk_files)} APK(s)")
            if stdout:
                console.print(f"[dim]{stdout.strip()}[/dim]")
        else:
            console.print(f"[red]✗[/red] Installation failed")
            if stderr:
                console.print(f"[red]Error:[/red] {stderr.strip()}")
            if stdout:
                console.print(f"[dim]{stdout.strip()}[/dim]")
            sys.exit(1)

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


def _display_activity_stack(device):
    """Internal helper to display activity stack.

    Args:
        device: Device serial number (optional)
    """
    adb = DeviceManager.get_adb(device)
    resolver = PackageResolver(adb)

    all_activities = resolver.get_top_activities()

    if not all_activities:
        console.print("[yellow]No activities found[/yellow]")
        return

    console.print(f"[bold cyan]Activity Stack ({len(all_activities)} activities):[/bold cyan]\n")

    # Create a nice table
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Activity", style="green")

    for idx, activity in enumerate(all_activities, 1):
        # Split activity and type if present
        parts = activity.split(' ', 1)
        activity_name = parts[0]
        activity_type = parts[1] if len(parts) > 1 else ""

        if activity_type:
            display = f"{activity_name} [dim]({activity_type})[/dim]"
        else:
            display = activity_name

        table.add_row(str(idx), display)

    console.print(table)


@app.command()
@click.option('-d', '--device', help='Device serial number')
def activity(device):
    """Show current foreground activity.

    Displays the current top activity in format: package/activity
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)

        top_activity = resolver.get_top_activity()
        if top_activity:
            console.print(top_activity)
        else:
            console.print("[yellow]No activity found[/yellow]")
            sys.exit(1)

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command()
@click.option('-d', '--device', help='Device serial number')
def activities(device):
    """Show all activities in the stack.

    Displays all activities from dumpsys activity activities.
    """
    try:
        _display_activity_stack(device)
    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@app.command(name='activitys')
@click.option('-d', '--device', help='Device serial number')
def activitys_alias(device):
    """Show all activities in the stack (alias for activities).

    Displays all activities from dumpsys activity activities.
    """
    try:
        _display_activity_stack(device)
    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
