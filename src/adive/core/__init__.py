"""Core package for Android Debug Tools.

This package provides the foundational components for interacting with Android devices:
- ADB: Low-level ADB command execution wrapper
- DeviceManager: Device selection and management
- PackageResolver: Package name resolution and validation
- Utility functions: Shell escaping, PID validation, UID resolution, etc.
"""
from .adb import ADB, ADBError
from .device import DeviceManager
from .package import PackageResolver
from .utils import (
    is_piped,
    validate_package_name,
    escape_shell_arg,
    validate_pid,
    resolve_uid,
    resolve_numeric_uid
)

__all__ = [
    'ADB',
    'ADBError',
    'DeviceManager',
    'PackageResolver',
    'is_piped',
    'validate_package_name',
    'escape_shell_arg',
    'validate_pid',
    'resolve_uid',
    'resolve_numeric_uid'
]
