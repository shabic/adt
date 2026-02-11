"""ADB wrapper for executing adb commands."""
import subprocess
import shutil
from typing import Optional, List, Tuple


class ADBError(Exception):
    """Exception raised for ADB-related errors."""
    pass


class ADB:
    """Wrapper for ADB (Android Debug Bridge) commands."""

    def __init__(self, device_id: Optional[str] = None):
        """Initialize ADB wrapper.

        Args:
            device_id: Optional device serial number. If None, uses default device.
        """
        self.device_id = device_id
        self._check_adb()

    def _check_adb(self):
        """Check if adb is available in PATH."""
        if not shutil.which("adb"):
            raise ADBError(
                "adb not found in PATH. Please install Android SDK Platform Tools."
            )

    def _build_command(self, args: List[str]) -> List[str]:
        """Build adb command with device selection.

        Args:
            args: Command arguments

        Returns:
            Complete command list
        """
        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)
        return cmd

    def execute(self, args: List[str], check: bool = True) -> Tuple[str, str, int]:
        """Execute adb command.

        Args:
            args: Command arguments
            check: Whether to raise exception on non-zero exit code

        Returns:
            Tuple of (stdout, stderr, returncode)

        Raises:
            ADBError: If command fails and check=True
        """
        cmd = self._build_command(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            if check and result.returncode != 0:
                raise ADBError(
                    f"Command failed: {' '.join(cmd)}\n"
                    f"Error: {result.stderr.strip()}"
                )

            return result.stdout, result.stderr, result.returncode
        except FileNotFoundError:
            raise ADBError("adb command not found")
        except Exception as e:
            raise ADBError(f"Failed to execute adb command: {e}")

    def shell(self, command: str, root: bool = False, check: bool = True) -> str:
        """Execute shell command on device.

        Args:
            command: Shell command to execute
            root: Whether to execute as root (using su)
            check: Whether to raise exception on non-zero exit code

        Returns:
            Command output (stdout)
        """
        if root:
            # Properly escape single quotes to prevent command injection
            escaped_command = command.replace("'", "'\"'\"'")
            command = f"su -c '{escaped_command}'"

        stdout, stderr, returncode = self.execute(["shell", command], check=check)
        return stdout.strip()

    def shell_interactive(self, command: str, root: bool = False) -> int:
        """Execute shell command with stdin/stdout/stderr inherited from terminal.

        Use this for long-running or interactive commands (e.g., tcpdump, top).

        Returns:
            Process exit code
        """
        if root:
            escaped_command = command.replace("'", "'\"'\"'")
            command = f"su -c '{escaped_command}'"

        cmd = self._build_command(["shell", command])
        try:
            result = subprocess.run(cmd)
            return result.returncode
        except KeyboardInterrupt:
            return 130
        except FileNotFoundError:
            raise ADBError("adb command not found")

    def pull(self, remote: str, local: str) -> None:
        """Pull file from device.

        Args:
            remote: Remote file path on device
            local: Local destination path
        """
        self.execute(["pull", remote, local])

    def push(self, local: str, remote: str) -> None:
        """Push file to device.

        Args:
            local: Local file path
            remote: Remote destination path on device
        """
        self.execute(["push", local, remote])

    def forward(self, local_port: int, remote_port: int) -> None:
        """Setup port forwarding.

        Args:
            local_port: Local TCP port
            remote_port: Remote TCP port on device
        """
        self.execute(["forward", f"tcp:{local_port}", f"tcp:{remote_port}"])

    def uninstall(self, package: str) -> None:
        """Uninstall package from device.

        Args:
            package: Package name to uninstall
        """
        self.execute(["uninstall", package])

    @staticmethod
    def list_devices() -> List[Tuple[str, str]]:
        """List all connected devices.

        Returns:
            List of (device_id, status) tuples
        """
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            devices = []
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                line = line.strip()
                if line:
                    parts = line.split('\t')
                    if len(parts) == 2:
                        devices.append((parts[0], parts[1]))

            return devices
        except Exception as e:
            raise ADBError(f"Failed to list devices: {e}")
