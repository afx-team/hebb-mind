"""CLI entry point."""

from __future__ import annotations

import click

from hebb import __version__
from hebb.cli.commands.config import config_cmd
from hebb.cli.commands.console import console_cmd
from hebb.cli.commands.doctor import doctor_cmd
from hebb.cli.commands.mcp_cmd import mcp_cmd
from hebb.cli.commands.memory import memory_cmd
from hebb.cli.commands.model import model_cmd
from hebb.cli.commands.serve import serve_cmd
from hebb.cli.commands.service import service_cmd
from hebb.cli.commands.setup import setup_cmd
from hebb.cli.commands.status import status_cmd
from hebb.cli.commands.upgrade import upgrade_cmd
from hebb.integrations.claude_code.cli import cc
from hebb.integrations.codex.cli import codex


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Hebb Mind -- Neuroscience-inspired memory framework for AI agents."""
    pass


main.add_command(setup_cmd, "setup")
main.add_command(service_cmd, "service")
main.add_command(status_cmd, "status")
main.add_command(console_cmd, "console")
main.add_command(config_cmd, "config")
main.add_command(mcp_cmd, "mcp")
main.add_command(model_cmd, "model")
main.add_command(memory_cmd, "memory")
main.add_command(doctor_cmd, "doctor")
main.add_command(upgrade_cmd, "upgrade")
main.add_command(cc)
main.add_command(codex)
# Hidden internal entrypoint invoked by the OS service manager (launchd /
# systemd / Task Scheduler). Not part of the public CLI surface.
main.add_command(serve_cmd, "_serve")


if __name__ == "__main__":
    main()
