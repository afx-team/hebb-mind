"""CLI entry point."""

from __future__ import annotations

import click

from hebb import __version__
from hebb.cli.commands.config import config_cmd
from hebb.cli.commands.doctor import doctor_cmd
from hebb.cli.commands.init import init_cmd
from hebb.cli.commands.mcp_cmd import mcp_cmd
from hebb.cli.commands.model import model_cmd
from hebb.cli.commands.service import service_cmd
from hebb.cli.commands.setup import setup_cmd
from hebb.cli.commands.start import start_cmd
from hebb.cli.commands.status import status_cmd
from hebb.cli.commands.stop import restart_cmd, stop_cmd
from hebb.cli.commands.workspace import workspace_cmd
from hebb.integrations.claude_code.cli import cc
from hebb.integrations.codex.cli import codex


@click.group()
@click.version_option(version=__version__)
def main():
    """Hebb Mind -- Neuroscience-inspired memory framework for AI agents."""
    pass


main.add_command(init_cmd, "init")
main.add_command(setup_cmd, "setup")
main.add_command(start_cmd, "start")
main.add_command(stop_cmd, "stop")
main.add_command(restart_cmd, "restart")
main.add_command(status_cmd, "status")
main.add_command(config_cmd, "config")
main.add_command(mcp_cmd, "mcp")
main.add_command(model_cmd, "model")
main.add_command(doctor_cmd, "doctor")
main.add_command(service_cmd, "service")
main.add_command(workspace_cmd, "workspace")
main.add_command(cc)
main.add_command(codex)


if __name__ == "__main__":
    main()
