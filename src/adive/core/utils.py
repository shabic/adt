"""Utility functions for ADT."""
import re
import sys
from typing import Optional


def is_piped() -> bool:
    """Check if stdout is being piped.

    Returns:
        True if stdout is piped, False otherwise
    """
    return not sys.stdout.isatty()


def validate_package_name(package: str) -> bool:
    """Validate Android package name format.

    Args:
        package: Package name to validate

    Returns:
        True if valid, False otherwise
    """
    # Android package names: segments separated by dots, each starting with letter
    # Format: com.example.app (no consecutive dots, no leading/trailing dots)
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$', package))


def escape_shell_arg(arg: str) -> str:
    """Escape single quotes in shell argument.

    This prevents command injection when using single-quoted strings in shell commands.

    Args:
        arg: Argument to escape

    Returns:
        Escaped argument safe for use in single-quoted shell strings
    """
    return arg.replace("'", "'\"'\"'")


def validate_pid(pid: str) -> bool:
    """Validate that PID is a valid numeric string.

    Args:
        pid: PID string to validate

    Returns:
        True if valid, False otherwise
    """
    return pid.isascii() and pid.isdigit()


def resolve_uid(adb, pkg: str) -> Optional[str]:
    """Resolve the UID for an Android package.

    Tries stat on /data/data (requires root), falls back to parsing ps -A output.

    Args:
        adb: ADB instance
        pkg: Validated package name

    Returns:
        UID string, or None if not found
    """
    # Try stat (requires root)
    escaped_pkg = escape_shell_arg(pkg)
    stat_output = adb.shell(f"stat -c '%U' /data/data/{escaped_pkg}", root=True, check=False)

    if stat_output and not stat_output.startswith("stat:") and "No such file" not in stat_output:
        return stat_output.strip()

    # Fallback: parse ps -A and match exact process name
    ps_output = adb.shell("ps -A", check=False)
    if not ps_output:
        return None

    for line in ps_output.strip().split('\n'):
        if line.startswith('USER') or line.startswith('PID'):
            continue

        parts = line.split()
        if len(parts) >= 9:
            process_name = parts[-1]
            if process_name == pkg or process_name.startswith(f"{pkg}:"):
                return parts[0]

    return None
