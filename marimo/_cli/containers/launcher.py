# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import click
from click import echo

from marimo._cli.containers.docker import DockerEngine
from marimo._cli.containers.engine import (
    Cancelled,
    EngineFailure,
    LaunchRequest,
    PortMapping,
    StartFailure,
    WorkloadExit,
)
from marimo._cli.errors import MarimoCLIRuntimeError
from marimo._cli.print import green, muted
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._utils.url import is_url

if TYPE_CHECKING:
    from typing import Literal

    from marimo._cli.containers.engine import (
        CleanupResult,
        ContainerEngine,
        SessionResult,
    )

_ENGINE: ContainerEngine = DockerEngine()


def prompt_run_in_container(
    name: str | None, trusted: bool | None = None
) -> bool:
    if GLOBAL_SETTINGS.IN_SECURE_ENVIRONMENT:
        return False
    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        return False

    if trusted is not None:
        return not trusted

    if name is None or not is_url(name):
        return False

    if GLOBAL_SETTINGS.YES:
        return True

    if not sys.stdin.isatty():
        return False

    return click.confirm(
        "This notebook is hosted on a remote server.\n"
        + green("Would you like to run it in a container?", bold=True),
        default=True,
    )


def _report_result(
    result: SessionResult, cleanup: CleanupResult | None
) -> None:
    errors = []
    if isinstance(result, EngineFailure):
        errors.append(str(result))
    elif isinstance(result, Cancelled):
        echo("Received keyboard interrupt.")
    elif isinstance(result, WorkloadExit) and result.status != 0:
        errors.append(f"Notebook exited with status {result.status}.")

    if isinstance(cleanup, EngineFailure):
        errors.append(str(cleanup))
    elif cleanup is not None:
        if cleanup.state == "removed":
            echo(muted("Container removed."))
        else:
            echo(muted("Container is already absent."))

    if errors:
        raise MarimoCLIRuntimeError("\n".join(errors))


def run_in_container(
    file_path: str | None,
    mode: Literal["edit", "run"],
    *,
    port: int | None,
    debug: bool = False,
    execute_opengraph_generators: bool = False,
) -> None:
    echo(f"Starting {green('containerized')} marimo notebook")
    host = "0.0.0.0"
    if port is None:
        port = 8080

    command = ["uvx", "marimo"]
    if debug:
        command.append("-d")
    command.extend(
        [mode, "--sandbox", "--no-token", "-p", str(port), "--host", host]
    )
    if execute_opengraph_generators:
        command.append("--execute-opengraph-generators")
    if file_path is not None:
        command.append(file_path)

    request = LaunchRequest(
        image="ghcr.io/astral-sh/uv:0.9.25-python3.14-bookworm",
        argv=tuple(command),
        environment=(
            ("MARIMO_MANAGE_SCRIPT_METADATA", "true"),
            ("MARIMO_IN_SECURE_ENVIRONMENT", "true"),
        ),
        working_directory="/home",
        ports=(PortMapping(host=port, container=port),),
    )
    session = _ENGINE.start(request)
    if isinstance(session, StartFailure):
        _report_result(session.result, session.cleanup)
        return

    try:
        echo(f"Container ID: {muted(session.identity.container)}")
        echo(f"URL: {green(f'http://{host}:{port}')}")
        for line in session.logs():
            echo(line.removesuffix("\n"))
        result = session.exit_result()
    except KeyboardInterrupt:
        result = Cancelled()
    finally:
        cleanup = session.close()
    _report_result(result, cleanup)
