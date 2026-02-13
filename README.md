# ADT - Android Debug Tools

A modern Python CLI toolkit for Android debugging and exploration, providing enhanced adb commands with rich terminal output and interactive device selection.

Dive deep into your Android apps and devices.

## Features

- **App Management**: Get app info, kill, pull APKs, view activities
- **Process Information**: View memory maps, file descriptors, process status
- **Memory Dump**: Dump memory ranges or SO libraries from running processes
- **Data Operations**: Backup/restore app data, search in app data
- **Utilities**: Get device IP, system properties, execute root commands

## Installation

### Prerequisites

- Python 3.8 or higher
- Android SDK Platform Tools (adb must be in PATH)
- Optional: aapt2 for APK renaming functionality

### Install from source

```bash
cd adt
pip install -e .
```

This will install the `adt` command globally.

## Usage

### App Management

```bash
# Show app information (auto-detects foreground app)
adt current

# Show info for specific package
adt current com.example.app

# Kill foreground app
adt kill

# Pull base APK with version in filename
adt pull-apk

# Pull all APKs (including splits)
adt pull-apks

# Install split APKs from directory (default: current directory)
adt install-multiple

# Install split APKs from specific directory
adt install-multiple ./27.2.0.0/

# Install split APKs and replace existing app
adt install-multiple -r

# Clear app data
adt clean

# Uninstall app
adt uninstall

# List native libraries
adt libs

# Show app processes
adt ps

# Get app path
adt path

# Get numeric UID
adt uid

# Show current foreground activity
adt activity

# Show all activities in the stack
adt activities
```

### Memory Dump

```bash
# Dump a specific address range (requires root)
adt dump-memory 0x12345000 0x12346000 com.example.app

# Dump all readable regions of a specific SO (requires root)
adt dump-memory --so libc.so com.example.app

# Dump SO with custom output path
adt dump-memory --so libc.so -o /tmp/libc_dump.so com.example.app

# Omit package to auto-detect foreground app
adt dump-memory --so libc.so
```

### Data Operations

```bash
# Backup app data (requires root)
adt backup

# Restore app data (requires root)
adt restore backup.tar.gz
adt restore com.example.app backup.tar.gz

# Search in app data (requires root)
adt grep "pattern"
```

### Process Information

```bash
# Show memory maps (auto-selects process if multiple)
adt maps

# Show memory maps with filter (faster for large outputs)
adt maps --filter .so
adt maps --filter .dex
adt maps -f libnative

# Specify PID directly (skip process selection)
adt maps --pid 12345

# Show file descriptors
adt fds

# Show process status
adt status
```

**Multi-Process Selection:**

If an app has multiple processes, ADT will show an interactive menu:

```
Multiple processes found for com.example.app:

#  PID    Process Name                  Threads  Memory
1  12345  com.example.app               23       156 MB
2  12346  com.example.app:remote        8        45 MB
3  12347  com.example.app:push          5        32 MB

Select process [1]: 2
✓ Selected PID: 12346
```

### Input Commands

```bash
# Send text input to device
adt input-text "Hello World"
```

### Utilities

```bash
# Get device IP address
adt ip

# Get system property
adt getprop ro.build.version.release

# List all properties
adt getprop

# Execute command as root
adt su "ls /data/data"
```

### Multi-Device Support

If multiple devices are connected, ADT will show a beautiful interactive menu with device information:

```
Multiple devices found:
Fetching device info...

#  Device ID       Manufacturer  Model        Status
1  2816c5b         Xiaomi        MI 8         device
2  2A091FDH200F6P  HUAWEI        ELE-AL00     device

Select device [1]: 2
✓ Selected: 2A091FDH200F6P
```

Features:
- Color-coded table display
- Device ID highlighted in green
- Manufacturer and model shown in blue
- Status shown in yellow
- Automatic device info detection (manufacturer, model)
- Selection confirmation with checkmark
- Default selection (press Enter for device #1)

Or specify device explicitly:

```bash
adt current -d 2816c5b
```

## Dependencies

- **click**: CLI framework
- **rich**: Beautiful terminal output

## Notes

- Commands that accept `[PACKAGE]` will auto-detect the foreground app if not specified
- Process commands (`maps`, `fds`, `status`) use `ps -A` to detect all processes (not just main process)
- Process commands will automatically try root access if needed
- **Pipe-friendly**: When output is piped (e.g., `adive maps | grep xxx`), automatically selects first device/process
- Root commands require a rooted device with `su` available
- Memory dump uses `dd` on `/proc/pid/mem`, requires root
- `--so` mode dumps in-memory image (PT_LOAD segments only, not identical to on-disk file)

## Performance Tips

- Use `adt maps --filter <pattern>` to filter large outputs on the device side
- Process commands use direct output for maximum speed
- Filter examples: `--filter .so`, `--filter .dex`, `--filter libnative`
- When piping output, selection prompts are automatically skipped

## License

MIT
