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

    A modern CLI for Android debugging and reverse engineering.
    """
    pass


# Import command groups
from .commands import app, data, process, utils


# Register command groups
cli.add_command(app.app)
cli.add_command(data.data)
cli.add_command(process.proc)

# Register top-level commands from utils
for cmd_name, cmd_obj in utils.get_commands():
    cli.add_command(cmd_obj, cmd_name)

# Register input-text as top-level command
from .commands import input as input_cmd
cli.add_command(input_cmd.input_text, 'input-text')

# Register dump-memory as top-level command
from .commands.memory import dump_memory
cli.add_command(dump_memory)


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
