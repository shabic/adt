"""Package resolver for detecting current app and activities."""
import re
from typing import List, Optional
from .adb import ADB
from .utils import validate_package_name


class PackageResolver:
    """Resolver for package names and activities."""

    def __init__(self, adb: ADB):
        """Initialize package resolver.

        Args:
            adb: ADB instance
        """
        self.adb = adb

    def get_top_activities(self) -> List[str]:
        """Get all top activities from dumpsys.

        Returns:
            List of activity strings in format "package/activity"
        """
        # Get dumpsys output
        output = self.adb.shell("dumpsys activity activities")

        # Find lines with cmp=
        activities = []
        for line in output.split('\n'):
            if 'cmp=' in line:
                # Extract the component info
                line = line.strip()
                line = line.replace('intent=', '')
                line = line.replace('Intent ', '')
                line = line.replace('{', '')
                line = line.replace('}', '')
                line = line.strip()

                # Parse cmp= and typ= fields
                cmp = ''
                typ = ''
                for kv in line.split():
                    if kv.startswith('cmp='):
                        cmp = kv.split('=', 1)[1]
                    elif kv.startswith('typ='):
                        typ = kv.split('=', 1)[1]

                if cmp:
                    activity_str = cmp
                    if typ:
                        activity_str = f"{cmp} {typ}"
                    activities.append(activity_str)

        # Remove duplicates while preserving order
        seen = set()
        unique_activities = []
        for act in activities:
            if act not in seen:
                seen.add(act)
                unique_activities.append(act)

        return unique_activities

    def get_top_activity(self) -> Optional[str]:
        """Get the current top activity.

        Returns:
            Top activity string in format "package/activity" or None
        """
        activities = self.get_top_activities()
        return activities[0] if activities else None

    def get_top_package(self) -> Optional[str]:
        """Get the current foreground package name.

        Returns:
            Package name or None
        """
        activity = self.get_top_activity()
        if activity:
            # Extract package from "package/activity" format
            parts = activity.split('/')
            if parts:
                return parts[0].split()[0]  # Remove any trailing type info
        return None

    def resolve_package(self, package: Optional[str] = None) -> str:
        """Resolve package name, defaulting to current foreground app.

        Args:
            package: Optional package name. If None, uses current foreground app.

        Returns:
            Resolved package name

        Raises:
            ValueError: If package is None and no foreground app detected
        """
        if package:
            if not validate_package_name(package):
                raise ValueError(f"Invalid package name: {package}")
            return package

        top_package = self.get_top_package()
        if not top_package:
            raise ValueError(
                "Could not detect foreground app. Please specify package name explicitly."
            )

        if not validate_package_name(top_package):
            raise ValueError(f"Invalid package name detected: {top_package}")

        return top_package

    def get_version(self, package: str) -> str:
        """Get the version name of a package.

        Args:
            package: Package name

        Returns:
            Version string, or "unknown" if not found
        """
        try:
            dump_output = self.adb.shell(f"pm dump {package}")
            match = re.search(r'versionName=(.+)', dump_output)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return "unknown"
