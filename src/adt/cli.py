"""Main CLI entry point for ADT."""
import sys
import click
from rich.console import Console
from . import __version__
from .core import ADBError, DeviceManager

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """ADT - Android Debug Tools

    A modern CLI toolkit for Android debugging and development.
    """
    pass


# Import all commands
from .commands import app, data, process, utils, input as input_cmd
from .commands.memory import dump_memory

# Register app commands
cli.add_command(app.info, 'info')
cli.add_command(app.kill, 'kill')
cli.add_command(app.pull_apk, 'pull-apk')
cli.add_command(app.pull_apks, 'pull-apks')
cli.add_command(app.clean, 'clean')
cli.add_command(app.uninstall, 'uninstall')
cli.add_command(app.libs, 'libs')
cli.add_command(app.ps, 'ps')
cli.add_command(app.path, 'path')
cli.add_command(app.activity, 'activity')
cli.add_command(app.activities, 'activities')
cli.add_command(app.install_multiple, 'install-multiple')

# Register process commands
cli.add_command(process.maps, 'maps')
cli.add_command(process.fds, 'fds')
cli.add_command(process.status, 'status')

# Register data commands
cli.add_command(data.backup, 'backup')
cli.add_command(data.restore, 'restore')
cli.add_command(data.data_grep, 'grep')

# Register utility commands
for cmd_name, cmd_obj in utils.get_commands():
    cli.add_command(cmd_obj, cmd_name)

# Register other top-level commands
cli.add_command(input_cmd.input_text, 'input-text')
cli.add_command(dump_memory, 'dump-memory')


def main():
    """Main entry point."""
    try:
        cli()
    except ADBError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
