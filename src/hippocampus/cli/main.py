"""CLI entry point."""

from __future__ import annotations

import click

from hippocampus import __version__
from hippocampus.cli.commands.config import config_cmd
from hippocampus.cli.commands.init import init_cmd
from hippocampus.cli.commands.mcp_cmd import mcp_cmd
from hippocampus.cli.commands.service import service_cmd
from hippocampus.cli.commands.start import start_cmd
from hippocampus.cli.commands.status import status_cmd
from hippocampus.cli.commands.stop import restart_cmd, stop_cmd
from hippocampus.cli.commands.workspace import workspace_cmd
from hippocampus.integrations.claude_code.cli import cc


@click.group()
@click.version_option(version=__version__)
def main():
    """Hippocampus -- Neuroscience-inspired memory framework for AI agents."""
    pass


main.add_command(init_cmd, "init")
main.add_command(start_cmd, "start")
main.add_command(stop_cmd, "stop")
main.add_command(restart_cmd, "restart")
main.add_command(status_cmd, "status")
main.add_command(config_cmd, "config")
main.add_command(mcp_cmd, "mcp")
main.add_command(service_cmd, "service")
main.add_command(workspace_cmd, "workspace")
main.add_command(cc)
