# Adive - Android Dive Tools

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
cd adive
pip install -e .
```

This will install the `adive` command globally.

## Usage

### App Management

```bash
# Show app information (auto-detects foreground app)
adive current

# Show info for specific package
adive current com.example.app

# Kill foreground app
adive kill

# Pull base APK with version in filename
adive pull-apk

# Pull all APKs (including splits)
adive pull-apks

# Install split APKs from directory (default: current directory)
adive install-multiple

# Install split APKs from specific directory
adive install-multiple ./27.2.0.0/

# Install split APKs and replace existing app
adive install-multiple -r

# Clear app data
adive clean

# Uninstall app
adive uninstall

# List native libraries
adive libs

# Show app processes
adive ps

# Get app path
adive path

# Get numeric UID
adive uid

# Show current foreground activity
adive activity

# Show all activities in the stack
adive activities
```

### Memory Dump

```bash
# Dump a specific address range (requires root)
adive dump-memory 0x12345000 0x12346000 com.example.app

# Dump all readable regions of a specific SO (requires root)
adive dump-memory --so libc.so com.example.app

# Dump SO with custom output path
adive dump-memory --so libc.so -o /tmp/libc_dump.so com.example.app

# Omit package to auto-detect foreground app
adive dump-memory --so libc.so
```

### Data Operations

```bash
# Backup app data (requires root)
adive backup

# Restore app data (requires root)
adive restore backup.tar.gz
adive restore com.example.app backup.tar.gz

# Search in app data (requires root)
adive grep "pattern"
```

### Process Information

```bash
# Show memory maps (auto-selects process if multiple)
adive maps

# Show memory maps with filter (faster for large outputs)
adive maps --filter .so
adive maps --filter .dex
adive maps -f libnative

# Specify PID directly (skip process selection)
adive maps --pid 12345

# Show file descriptors
adive fds

# Show process status
adive status
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
adive input-text "Hello World"
```

### Utilities

```bash
# Get device IP address
adive ip

# Get system property
adive getprop ro.build.version.release

# List all properties
adive getprop

# Execute command as root
adive su "ls /data/data"
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
adive current -d 2816c5b
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

- Use `adive maps --filter <pattern>` to filter large outputs on the device side
- Process commands use direct output for maximum speed
- Filter examples: `--filter .so`, `--filter .dex`, `--filter libnative`
- When piping output, selection prompts are automatically skipped

## License

MIT
