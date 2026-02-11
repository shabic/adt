"""Process information commands."""
import click
import sys
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt
from ..core import DeviceManager, PackageResolver, ADBError, resolve_uid, escape_shell_arg, is_piped

console = Console()
console_stderr = Console(stderr=True)


def _validate_pid_arg(pid: str):
    """Validate PID argument and exit on invalid input."""
    if not (pid.isascii() and pid.isdigit()):
        console.print(f"[red]Error:[/red] Invalid PID: {pid}")
        sys.exit(1)


def _select_process(adb, pkg: str) -> str:
    """Select process if multiple PIDs exist.

    Args:
        adb: ADB instance
        pkg: Package name

    Returns:
        Selected PID as string

    Raises:
        SystemExit: If no processes found
    """
    uid = resolve_uid(adb, pkg)
    if not uid:
        console.print(f"[red]Error:[/red] App {pkg} is not running")
        sys.exit(1)

    # Get ALL processes with this UID (includes all app processes)
    # Use grep -wF for exact word + literal matching
    escaped_uid = escape_shell_arg(uid)
    all_ps_output = adb.shell(f"ps -A | grep -wF '{escaped_uid}'", check=False)
    if not all_ps_output:
        console.print(f"[red]Error:[/red] Could not get process list")
        sys.exit(1)

    # Parse all processes to get PIDs
    pids = []
    ps_lines = []
    for line in all_ps_output.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 2:
            # Second column is PID in ps output
            pid = parts[1]
            # Validate PID is ASCII digits only (not Unicode digits)
            if pid.isascii() and pid.isdigit():
                pids.append(pid)
                ps_lines.append(line)

    if not pids:
        console.print(f"[red]Error:[/red] App {pkg} is not running")
        sys.exit(1)

    # If only one PID, return it
    if len(pids) == 1:
        return pids[0]

    # Check if output is piped - if so, auto-select first process
    if is_piped():
        console_stderr.print(f"[dim]Auto-selecting first process (PID: {pids[0]}) - output is piped[/dim]")
        return pids[0]

    # Multiple PIDs - get process info and let user select
    console_stderr.print(f"\n[bold cyan]Multiple processes found for {pkg}:[/bold cyan]")

    # Get process info for each PID
    process_info = []
    for pid in pids:
        # Get process name from /proc/PID/cmdline
        cmdline = adb.shell(f"cat /proc/{pid}/cmdline", check=False).strip()
        # cmdline uses null bytes as separators, replace with spaces
        cmdline = cmdline.replace('\x00', ' ').strip()
        if not cmdline:
            # Fallback: try to extract from ps output
            for ps_line in ps_lines:
                if f" {pid} " in ps_line:
                    # Last column is usually the process name
                    parts = ps_line.split()
                    if len(parts) >= 9:
                        cmdline = parts[8]
                    break
            if not cmdline:
                cmdline = pkg

        # Get process status (threads, memory, etc)
        status_output = adb.shell(f"cat /proc/{pid}/status", check=False)
        threads = "?"
        vmsize = "?"

        for line in status_output.split('\n'):
            if line.startswith('Threads:'):
                threads = line.split(':')[1].strip()
            elif line.startswith('VmSize:'):
                vmsize = line.split(':')[1].strip()

        process_info.append((pid, cmdline, threads, vmsize))

    # Create table
    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
    table.add_column("#", style="cyan", justify="right")
    table.add_column("PID", style="green")
    table.add_column("Process Name", style="blue")
    table.add_column("Threads", style="yellow")
    table.add_column("Memory", style="yellow")

    for idx, (pid, cmdline, threads, vmsize) in enumerate(process_info, 1):
        # Truncate long process names
        if len(cmdline) > 40:
            cmdline = cmdline[:37] + "..."
        table.add_row(str(idx), pid, cmdline, threads, vmsize)

    console_stderr.print(table)

    # Prompt for selection
    while True:
        try:
            choice = IntPrompt.ask(
                "[bold cyan]Select process[/bold cyan]",
                default=1,
                console=console_stderr
            )
            if 1 <= choice <= len(pids):
                selected_pid = pids[choice - 1]
                console_stderr.print(f"[green]✓[/green] Selected PID: [bold]{selected_pid}[/bold]\n")
                return selected_pid
            else:
                console_stderr.print(f"[red]✗[/red] Invalid choice. Please enter 1-{len(pids)}")
        except (ValueError, KeyboardInterrupt):
            console_stderr.print("\n[yellow]Process selection cancelled[/yellow]")
            sys.exit(1)


@click.group()
def proc():
    """Process information commands."""
    pass


@proc.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-f', '--filter', help='Filter maps by pattern (e.g., .so, .dex)')
@click.option('-p', '--pid', help='Specific PID (skip process selection)')
def maps(package, device, filter, pid):
    """Show process memory maps (/proc/PID/maps).

    If PACKAGE is not provided, uses the current foreground app.
    If multiple processes exist, prompts for selection.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        # Get PID - either specified or selected
        if pid:
            _validate_pid_arg(pid)
            selected_pid = pid
        else:
            selected_pid = _select_process(adb, pkg)

        # Build command - use grep filter if provided for faster output
        if filter:
            # Escape single quotes in filter to prevent injection
            escaped_filter = filter.replace("'", "'\"'\"'")
            # Use grep -F for literal matching (safer)
            cmd = f"cat /proc/{selected_pid}/maps | grep -F '{escaped_filter}'"
            console.print(f"[bold cyan]Memory maps for {pkg} (PID: {selected_pid}) - filtered by '{filter}':[/bold cyan]\n")
        else:
            cmd = f"cat /proc/{selected_pid}/maps"
            console.print(f"[bold cyan]Memory maps for {pkg} (PID: {selected_pid}):[/bold cyan]\n")

        # Try without root first
        maps_output = adb.shell(cmd, root=False, check=False)

        # If empty or permission denied, try with root
        if not maps_output or 'Permission denied' in maps_output or 'cannot open' in maps_output:
            maps_output = adb.shell(cmd, root=True, check=False)

        # Print directly without rich formatting for speed
        if maps_output:
            sys.stdout.write(maps_output)
            sys.stdout.write('\n')
        else:
            console.print("[yellow]No output or permission denied. Try running with root access.[/yellow]")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@proc.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-p', '--pid', help='Specific PID (skip process selection)')
def fds(package, device, pid):
    """Show process file descriptors (/proc/PID/fd).

    If PACKAGE is not provided, uses the current foreground app.
    If multiple processes exist, prompts for selection.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        # Get PID - either specified or selected
        if pid:
            _validate_pid_arg(pid)
            selected_pid = pid
        else:
            selected_pid = _select_process(adb, pkg)

        console.print(f"[bold cyan]File descriptors for {pkg} (PID: {selected_pid}):[/bold cyan]\n")

        # Try without root first
        fds_output = adb.shell(f"ls -l /proc/{selected_pid}/fd", root=False, check=False)

        # If permission denied, try with root
        if not fds_output or 'Permission denied' in fds_output or 'cannot access' in fds_output:
            fds_output = adb.shell(f"ls -l /proc/{selected_pid}/fd", root=True, check=False)

        # Print with Rich
        if fds_output:
            console.print(fds_output)
        else:
            console.print("[yellow]No output or permission denied. Try running with root access.[/yellow]")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@proc.command()
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-p', '--pid', help='Specific PID (skip process selection)')
def status(package, device, pid):
    """Show process status (/proc/PID/status).

    If PACKAGE is not provided, uses the current foreground app.
    If multiple processes exist, prompts for selection.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)
        pkg = resolver.resolve_package(package)

        # Get PID - either specified or selected
        if pid:
            _validate_pid_arg(pid)
            selected_pid = pid
        else:
            selected_pid = _select_process(adb, pkg)

        console.print(f"[bold cyan]Process status for {pkg} (PID: {selected_pid}):[/bold cyan]\n")

        # Try without root first
        status_output = adb.shell(f"cat /proc/{selected_pid}/status", root=False, check=False)

        # If permission denied, try with root
        if not status_output or 'Permission denied' in status_output or 'cannot open' in status_output:
            status_output = adb.shell(f"cat /proc/{selected_pid}/status", root=True, check=False)

        # Print with Rich
        if status_output:
            console.print(status_output)
        else:
            console.print("[yellow]No output or permission denied. Try running with root access.[/yellow]")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
