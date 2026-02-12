# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2025-02-10

### Added

- App management: current, kill, pull-apk, pull-apks, install-multiple, clean, uninstall, libs, ps, path, uid
- Process inspection: maps, fds, status with multi-process interactive selection
- Memory dump: address range dump and `--so` mode for SO library dumping via `dd`
- Data operations: backup, restore, grep (requires root)
- Input commands: text input
- Utilities: ip, getprop, su
- Multi-device support with interactive device selection
- Pipe-friendly output (auto-selects first device/process when piped)
- Rich terminal output with color-coded tables
- Security hardening: shell argument escaping, input validation, package name validation
