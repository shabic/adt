"""Memory dump command."""
import os
import struct
import sys
import click
from rich.console import Console
from rich.prompt import IntPrompt
from rich.table import Table
from ..core import DeviceManager, PackageResolver, ADBError, is_piped
from .process import _select_process

console = Console()
console_stderr = Console(stderr=True)

_MAX_PHNUM = 4096
_MAX_PH_ENTRY_SIZE = 256
_MAX_PH_TOTAL_SIZE = 8 * 1024 * 1024
_ZERO_FILL_CHUNK = 1024 * 1024


def _load_maps_entries(adb, pid):
    """Load /proc/<pid>/maps entries as sorted tuples."""
    maps_output = adb.shell(f"cat /proc/{pid}/maps", root=True, check=False)
    entries = []
    if not maps_output:
        return entries

    for line in maps_output.strip().split('\n'):
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue

        addr_range = parts[0].split('-')
        if len(addr_range) != 2:
            continue

        try:
            start = int(addr_range[0], 16)
            end = int(addr_range[1], 16)
        except ValueError:
            continue

        perms = parts[1]
        path = parts[5].strip() if len(parts) >= 6 else ""
        entries.append((start, end, perms, path))

    entries.sort(key=lambda x: x[0])
    return entries


def _segment_readable_now(adb, pid, start_addr, end_addr):
    """Check whether [start_addr, end_addr) is fully readable right now."""
    entries = _load_maps_entries(adb, pid)
    if not entries:
        return False

    cursor = start_addr
    for start, end, perms, _ in entries:
        if end <= cursor:
            continue
        if start > cursor:
            return False
        if 'r' not in perms:
            return False

        cursor = min(end_addr, end)
        if cursor >= end_addr:
            return True

    return False


def _parse_ls_size(ls_output):
    """Parse file size from `ls -l` output."""
    parts = ls_output.strip().split()
    if len(parts) < 5:
        return None
    try:
        return int(parts[4])
    except ValueError:
        return None


def _path_total_size(entries):
    """Calculate total bytes for a path group."""
    return sum((end - start) for start, end, _ in entries)


def _find_so_segments(adb, pid, so_name):
    """Find readable memory segments and matching maps lines for a given SO.

    Groups by full path. If multiple paths match, prompts user to select.
    Skips non-readable segments (no 'r' in permission bits).

    Returns ([(start, end), ...], [matching_lines]) or ([], []).
    """
    maps_output = adb.shell(f"cat /proc/{pid}/maps", root=True, check=False)
    if not maps_output:
        return [], []

    # Group matching segments by full path
    # path_groups: {pathname: [(start, end, line), ...]}
    path_groups = {}
    for line in maps_output.strip().split('\n'):
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        perms = parts[1]
        if 'r' not in perms:
            continue
        pathname = parts[5].strip()
        # Strip " (deleted)" suffix for matching
        clean_path = pathname
        if clean_path.endswith(' (deleted)'):
            clean_path = clean_path[:-len(' (deleted)')]
        if not clean_path.endswith('/' + so_name) and clean_path != so_name:
            continue
        addr_range = parts[0].split('-')
        start = int(addr_range[0], 16)
        end = int(addr_range[1], 16)
        path_groups.setdefault(pathname, []).append((start, end, line))

    if not path_groups:
        return [], []

    # If multiple distinct paths, let user choose
    if len(path_groups) > 1:
        paths = sorted(path_groups.keys())
        if is_piped():
            selected_path = sorted(
                paths,
                key=lambda p: (-_path_total_size(path_groups[p]), p)
            )[0]
            console_stderr.print(
                f"[dim]Auto-selecting {selected_path} (output is piped)[/dim]"
            )
        else:
            console_stderr.print(f"\n[bold cyan]Multiple paths found for {so_name}:[/bold cyan]")
            table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Path", style="blue")
            table.add_column("Segments", style="yellow", justify="right")
            table.add_column("Readable Bytes", style="yellow", justify="right")
            for idx, path in enumerate(paths, 1):
                table.add_row(
                    str(idx),
                    path,
                    str(len(path_groups[path])),
                    f"0x{_path_total_size(path_groups[path]):x}",
                )
            console_stderr.print(table)
            while True:
                try:
                    choice = IntPrompt.ask(
                        "[bold cyan]Select library[/bold cyan]",
                        default=1,
                        console=console_stderr
                    )
                    if 1 <= choice <= len(paths):
                        selected_path = paths[choice - 1]
                        console_stderr.print(f"[green]✓[/green] Selected: [bold]{selected_path}[/bold]\n")
                        break
                    console_stderr.print(f"[red]Please enter 1-{len(paths)}[/red]")
                except (KeyboardInterrupt, EOFError):
                    sys.exit(1)
        selected_entries = path_groups[selected_path]
    else:
        selected_entries = list(path_groups.values())[0]

    selected_entries.sort(key=lambda x: x[0])
    segments = [(start, end) for start, end, _ in selected_entries]
    matched_lines = [line for _, _, line in selected_entries]

    return segments, matched_lines


def _read_mem(adb, pid, addr, size):
    """Read raw bytes from /proc/{pid}/mem at given address."""
    remote_tmp = f"/data/local/tmp/memread_{pid}_{addr:x}.bin"
    dd_cmd = (
        f"dd if=/proc/{pid}/mem of={remote_tmp}"
        f" bs=1 iflag=skip_bytes,count_bytes skip={addr} count={size}"
        f" 2>&1"
    )
    dd_output = adb.shell(dd_cmd, root=True, check=False)

    check = adb.shell(f"ls -l {remote_tmp}", root=True, check=False)
    if not check or "No such file" in check:
        if dd_output:
            console.print(f"[yellow]dd:[/yellow] {dd_output.strip()}")
        return None

    actual_size = _parse_ls_size(check)
    if actual_size is None or actual_size != size:
        console.print(
            f"[yellow]Warning:[/yellow] read expected {size} bytes from 0x{addr:x}, got {actual_size}"
        )
        adb.shell(f"rm {remote_tmp}", root=True, check=False)
        return None

    local_tmp = remote_tmp.replace('/', '_') + '.tmp'
    try:
        adb.pull(remote_tmp, local_tmp)
        with open(local_tmp, 'rb') as f:
            data = f.read()
    finally:
        adb.shell(f"rm {remote_tmp}", root=True, check=False)
        if os.path.exists(local_tmp):
            os.remove(local_tmp)
    return data


def _detect_elf_arch(adb, pid, base_addr):
    """Detect ELF class and machine type from header.

    Returns (ei_class, arch_name) or (None, None).
    ei_class: 1=32bit, 2=64bit
    """
    ehdr = _read_mem(adb, pid, base_addr, 20)
    if not ehdr or len(ehdr) < 20:
        return None, None

    if ehdr[:4] != b'\x7fELF':
        return None, None

    ei_class = ehdr[4]
    e_machine, = struct.unpack_from('<H', ehdr, 18)

    _MACHINES = {
        3: 'x86', 40: 'ARM', 62: 'x86_64', 183: 'AArch64',
        8: 'MIPS', 243: 'RISC-V',
    }
    arch = _MACHINES.get(e_machine, f'EM_{e_machine}')
    bits = {1: '32', 2: '64'}.get(ei_class, '?')
    return ei_class, f"{arch}({bits}bit)"


def _parse_elf_size(adb, pid, base_addr, ei_class=None):
    """Parse ELF header + program headers to determine SO size in memory.

    Returns total size or None on failure.
    If ei_class is provided, skip re-reading the ELF header class.
    """
    # Read ELF header (64 bytes for ELF64, 52 for ELF32)
    ehdr = _read_mem(adb, pid, base_addr, 64)
    if not ehdr or len(ehdr) < 52:
        return None

    if ei_class is None:
        ei_class = ehdr[4]

    if ei_class == 2:
        # ELF64: e_phoff(8B)@32, e_phentsize(2B)@54, e_phnum(2B)@56
        e_phoff, = struct.unpack_from('<Q', ehdr, 32)
        e_phentsize, = struct.unpack_from('<H', ehdr, 54)
        e_phnum, = struct.unpack_from('<H', ehdr, 56)
    elif ei_class == 1:
        # ELF32: e_phoff(4B)@28, e_phentsize(2B)@42, e_phnum(2B)@44
        e_phoff, = struct.unpack_from('<I', ehdr, 28)
        e_phentsize, = struct.unpack_from('<H', ehdr, 42)
        e_phnum, = struct.unpack_from('<H', ehdr, 44)
    else:
        return None

    # Read program headers
    if e_phnum <= 0 or e_phentsize <= 0:
        return None
    if e_phnum > _MAX_PHNUM or e_phentsize > _MAX_PH_ENTRY_SIZE:
        return None
    ph_size = e_phentsize * e_phnum
    if ph_size > _MAX_PH_TOTAL_SIZE:
        return None
    phdata = _read_mem(adb, pid, base_addr + e_phoff, ph_size)
    if not phdata or len(phdata) < ph_size:
        return None

    # PT_LOAD = 1, find min(p_vaddr) and max(p_vaddr + p_memsz)
    min_vaddr = None
    max_end = 0
    for i in range(e_phnum):
        off = i * e_phentsize
        if off + e_phentsize > len(phdata):
            return None
        if ei_class == 2:
            if off + 48 > len(phdata):
                return None
            p_type, = struct.unpack_from('<I', phdata, off)
            if p_type != 1:
                continue
            p_vaddr, = struct.unpack_from('<Q', phdata, off + 16)
            p_memsz, = struct.unpack_from('<Q', phdata, off + 40)
        else:
            if off + 24 > len(phdata):
                return None
            p_type, = struct.unpack_from('<I', phdata, off)
            if p_type != 1:
                continue
            p_vaddr, = struct.unpack_from('<I', phdata, off + 8)
            p_memsz, = struct.unpack_from('<I', phdata, off + 20)
        if min_vaddr is None or p_vaddr < min_vaddr:
            min_vaddr = p_vaddr
        end = p_vaddr + p_memsz
        if end > max_end:
            max_end = end

    if min_vaddr is None:
        return None
    size = max_end - min_vaddr
    if size <= 0:
        return None
    return size


def _dump_region(adb, pid, start_addr, end_addr, output, strict_size=True):
    """Dump a single memory region to a local file."""
    size = end_addr - start_addr
    remote_tmp = f"/data/local/tmp/memdump_{pid}_{start_addr:x}_{end_addr:x}.bin"
    dd_cmd = (
        f"dd if=/proc/{pid}/mem of={remote_tmp}"
        f" bs=4096 iflag=skip_bytes,count_bytes skip={start_addr} count={size}"
        f" 2>&1"
    )
    dd_output = adb.shell(dd_cmd, root=True, check=False)

    check = adb.shell(f"ls -l {remote_tmp}", root=True, check=False)
    if not check or "No such file" in check:
        if dd_output:
            console.print(f"[yellow]dd:[/yellow] {dd_output.strip()}")
        return False

    actual_size = _parse_ls_size(check)
    if actual_size is None:
        console.print("[yellow]Warning:[/yellow] could not parse remote dump size")
        if strict_size:
            adb.shell(f"rm {remote_tmp}", root=True, check=False)
            return False
    elif actual_size != size:
        console.print(
            f"[yellow]Warning:[/yellow] expected 0x{size:x} ({size}) bytes, "
            f"got 0x{actual_size:x} ({actual_size}) bytes"
        )
        if strict_size:
            adb.shell(f"rm {remote_tmp}", root=True, check=False)
            return False

    try:
        adb.pull(remote_tmp, output)
    finally:
        adb.shell(f"rm {remote_tmp}", root=True, check=False)
    return True


def _write_zeros(file_obj, size):
    """Write zero bytes without allocating one huge buffer."""
    chunk = b'\x00' * _ZERO_FILL_CHUNK
    remaining = size
    while remaining > 0:
        to_write = min(remaining, _ZERO_FILL_CHUNK)
        file_obj.write(chunk[:to_write])
        remaining -= to_write


def _dump_so_segments(adb, pid, segments, output):
    """Dump readable SO segments and stitch them with zero-filled gaps."""
    if not segments:
        return False

    base_addr = segments[0][0]
    tmp_files = []
    success = False

    try:
        for start, end in segments:
            if not _segment_readable_now(adb, pid, start, end):
                console.print(
                    f"[red]Error:[/red] segment 0x{start:x}-0x{end:x} "
                    "is no longer readable (possible anti-dump behavior)"
                )
                return False

            tmp_file = f"{output}.part_{start:x}_{end:x}.tmp"
            if not _dump_region(adb, pid, start, end, tmp_file, strict_size=True):
                if not _segment_readable_now(adb, pid, start, end):
                    console.print(
                        f"[red]Error:[/red] segment 0x{start:x}-0x{end:x} "
                        "became unreadable during dump (possible anti-dump behavior)"
                    )
                return False
            tmp_files.append((start, end, tmp_file))

        with open(output, 'wb') as out:
            pos = base_addr
            for start, end, tmp_file in tmp_files:
                if start > pos:
                    _write_zeros(out, start - pos)

                expected_size = end - start
                written = 0
                with open(tmp_file, 'rb') as part:
                    while True:
                        chunk = part.read(_ZERO_FILL_CHUNK)
                        if not chunk:
                            break
                        written += len(chunk)
                        out.write(chunk)

                if written != expected_size:
                    console.print(
                        f"[red]Error:[/red] segment 0x{start:x}-0x{end:x} size mismatch: "
                        f"expected {expected_size}, got {written}"
                    )
                    return False

                pos = end

        success = True
        return True
    finally:
        if not success and os.path.exists(output):
            os.remove(output)
        for _, _, tmp_file in tmp_files:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)


@click.command('dump-memory')
@click.argument('start', required=False)
@click.argument('end', required=False)
@click.argument('package', required=False)
@click.option('-d', '--device', help='Device serial number')
@click.option('-o', '--output', help='Output file path')
@click.option('--so', 'so_name', help='Dump a specific SO library (e.g., libc.so)')
def dump_memory(start, end, package, device, output, so_name):
    """Dump memory range from app via dd.

    \b
    Two modes:
      adt dump-memory START END [PACKAGE]     Dump a specific address range
      adt dump-memory --so libc.so [PACKAGE]  Dump all readable regions of a SO

    START and END should be hex addresses (e.g., 0x12345000).
    In --so mode, PACKAGE can be passed as the first positional arg.
    If PACKAGE is not provided, uses the current foreground app.
    Requires root access.
    """
    try:
        adb = DeviceManager.get_adb(device)
        resolver = PackageResolver(adb)

        if so_name:
            if end or (start and package):
                console.print(
                    "[red]Error:[/red] --so mode accepts only one positional PACKAGE argument"
                )
                sys.exit(1)

            # --so mode: package can be in start or package positional arg
            pkg = resolver.resolve_package(start or package)
            pid = _select_process(adb, pkg)

            cmdline = adb.shell(f"cat /proc/{pid}/cmdline", check=False).strip()
            proc_name = cmdline.replace('\x00', ' ').strip() or pkg

            console.print(f"Process: [cyan]{proc_name}[/cyan] (PID {pid})")
            console.print(f"Searching maps for [cyan]{so_name}[/cyan]...")

            segments, matched_lines = _find_so_segments(adb, pid, so_name)
            if not segments:
                console.print(f"[red]Error:[/red] {so_name} not found in /proc/{pid}/maps")
                sys.exit(1)

            for line in matched_lines:
                console.print(line)

            base_addr = segments[0][0]
            end_addr = segments[-1][1]
            total_size = sum(end - start for start, end in segments)

            # Detect architecture
            ei_class, arch_name = _detect_elf_arch(adb, pid, base_addr)
            if arch_name:
                console.print(f"Arch: [cyan]{arch_name}[/cyan]")

            out_file = output or so_name

            console.print(
                f"Dumping {len(segments)} segment(s), "
                f"range 0x{base_addr:x}-0x{end_addr:x}, total 0x{total_size:x} bytes"
            )

            if not _dump_so_segments(adb, pid, segments, out_file):
                console.print("[red]Error:[/red] dump failed, some memory segment is unreadable")
                sys.exit(1)

            console.print(f"[green]✓[/green] {out_file}")

        else:
            # Address range mode
            if not start or not end:
                console.print("[red]Error:[/red] START and END are required (or use --so)")
                sys.exit(1)

            pkg = resolver.resolve_package(package)

            try:
                start_addr = int(start, 16)
                end_addr = int(end, 16)
            except ValueError:
                console.print("[red]Error:[/red] START and END must be hex addresses (e.g., 0x12345000)")
                sys.exit(1)

            if end_addr <= start_addr:
                console.print("[red]Error:[/red] END address must be greater than START")
                sys.exit(1)

            size = end_addr - start_addr
            pid = _select_process(adb, pkg)

            cmdline = adb.shell(f"cat /proc/{pid}/cmdline", check=False).strip()
            proc_name = cmdline.replace('\x00', ' ').strip() or pkg

            if not output:
                output = f"{start}-{end}.bin"

            console.print(f"Process: [cyan]{proc_name}[/cyan] (PID {pid})")
            console.print(f"Dumping memory {start}-{end} (0x{size:x} bytes)")

            if not _dump_region(adb, pid, start_addr, end_addr, output):
                console.print("[red]Error:[/red] dd failed, memory region may not be readable")
                sys.exit(1)

            console.print(f"[green]✓[/green] Memory dump saved to: {output}")

    except (ADBError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
