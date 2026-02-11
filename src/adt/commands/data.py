"""Data operation commands."""
import sys
import click
from rich.console import Console
from ..core import DeviceManager, PackageResolver, ADBError

console = Console()


@click.group()
def data():
    """Data operation commands (backup, restore, grep)."""
    pass


@data.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-o', '--output', help='Output filename (default: <package>-<version>.tar.gz)')
def backup(package, device, output):
    """Backup app data to tar.gz.

    If PACKAGE is not provided, uses the current foreground app.
    Requires root access.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        # Get version for filename
        if not output:
            version = resolver.get_version(pkg)
            # Clean version string for filename
            version = version.replace('(', '').replace(')', '').replace(' ', '')
            output = f"{pkg}-{version}.tar.gz"

        console.print(f"Backing up {pkg}")

        # Create tar on device
        tar_name = f"{pkg}.tar.gz"
        tar_cmd = (
            f"tar -zcvf /data/local/tmp/{tar_name} "
            f"--exclude='/data/data/{pkg}/cache' "
            f"--exclude='/data/data/{pkg}/code_cache' "
            f"--exclude='/data/data/{pkg}/oat' "
            f"/data/data/{pkg}/"
        )

        adb.shell(tar_cmd, root=True)

        # Pull tar from device
        console.print(f"Pulling backup")
        adb.pull(f"/data/local/tmp/{tar_name}", output)

        # Clean up
        adb.shell(f"rm /data/local/tmp/{tar_name}", root=True, check=False)

        console.print(f"[green]✓[/green] Backup saved to: {output}")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@data.command()
@click.argument('package', required=False)
@click.argument('file', type=click.Path(exists=True))
@click.option('-d', '--device', help='Device serial number')
def restore(package, file, device):
    """Restore app data from tar.gz backup.

    If PACKAGE is not provided, uses the current foreground app.
    Requires root access.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        console.print(f"Restoring {pkg} from {file}")

        # Get app UID
        uid_output = adb.shell(f"ls -ld /data/data/{pkg} | tr -s ' ' | cut -d ' ' -f 4", root=True)
        uid = uid_output.strip()

        # Push backup to device
        console.print("Pushing backup to device")
        tar_name = f"{pkg}.tar.gz"
        adb.push(file, f"/data/local/tmp/{tar_name}")

        # Clear app data
        console.print("Clearing app data")
        adb.shell(f"pm clear {pkg}")

        # Extract backup
        console.print("Extracting backup")
        adb.shell(f"tar zxvf /data/local/tmp/{tar_name} -C /", root=True)

        # Fix permissions
        console.print("Fixing permissions")
        adb.shell(f"chown -R {uid}:{uid} /data/data/{pkg}/", root=True)

        # Launch app
        console.print("Launching app")
        adb.shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", check=False)

        # Clean up
        adb.shell(f"rm /data/local/tmp/{tar_name}", root=True, check=False)

        console.print(f"[green]✓[/green] Restored {pkg}")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@data.command()
@click.argument('pattern', required=True)
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
def grep(pattern, package, device):
    """Search for pattern in app data directory.

    If PACKAGE is not provided, uses the current foreground app.
    Requires root access.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        console.print(f"Searching for '{pattern}' in {pkg} data")

        # Escape single quotes in pattern to prevent injection
        # Use grep -F for literal matching (safer)
        escaped_pattern = pattern.replace("'", "'\"'\"'")
        result = adb.shell(f"grep -F -rn '{escaped_pattern}' /data/data/{pkg}/", root=True, check=False)

        if result:
            console.print(result)
        else:
            console.print(f"[yellow]No matches found[/yellow]")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
