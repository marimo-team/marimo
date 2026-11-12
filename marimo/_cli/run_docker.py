# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
from typing import Literal

import click
from click import echo

from marimo import _loggers
from marimo._cli.errors import MarimoCLIRuntimeError
from marimo._cli.print import green, muted, red
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.url import is_url

LOGGER = _loggers.marimo_logger()

# Container engines whose CLI accepts the same commands as docker,
# in order of preference.
CONTAINER_ENGINES = ("docker", "podman")


def prompt_run_in_docker_container(
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

    # Check if not in an interactive terminal
    # default to False
    if not sys.stdin.isatty():
        return False

    return click.confirm(
        "This notebook is hosted on a remote server.\n"
        + muted(
            "Supported container engines: "
            f"{', '.join(CONTAINER_ENGINES)} "
            "(the first one installed and running is used)\n"
        )
        + green(
            "Would you like to run it in a secure container?",
            bold=True,
        ),
        default=True,
    )


def _check_engine_running(engine: str) -> bool:
    try:
        subprocess.run(
            [engine, "info"],
            check=True,
            capture_output=True,
            text=True,
            # An unreachable engine can hang; give up so we can try the next.
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def _find_container_engine() -> str:
    problems: list[str] = []
    for engine in CONTAINER_ENGINES:
        if not DependencyManager.which(engine):
            problems.append(f"{engine}: not found")
        elif not _check_engine_running(engine):
            problems.append(
                f"{engine}: installed but not running or not responding"
            )
        else:
            return engine
    raise MarimoCLIRuntimeError(
        "No usable container engine found:\n"
        + "".join(f"  {problem}\n" for problem in problems)
        + "Please install or start one of them and try again."
    )


def echo_red(text: str) -> None:
    echo(red(text))


def _check_port_in_use(engine: str, port: int) -> str | None:
    try:
        result = subprocess.run(
            [engine, "ps", "--format", "{{.ID}}\t{{.Ports}}", "--no-trunc"],
            check=True,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            container_id, ports = line.split("\t")
            if f":{port}->" in ports:
                return container_id
    except subprocess.CalledProcessError:
        pass
    return None


def run_in_docker(
    file_path: str | None,
    mode: Literal["edit", "run"],
    *,
    port: int | None,
    debug: bool = False,
    execute_opengraph_generators: bool = False,
) -> None:
    engine = _find_container_engine()
    echo(f"Starting {green('containerized')} marimo notebook (using {engine})")

    host = "0.0.0.0"
    if port is None:
        port = 8080

    # Check if the port is already in use
    existing_container = _check_port_in_use(engine, port)
    if existing_container:
        stop_command = muted(f"{engine} stop {existing_container}")
        raise MarimoCLIRuntimeError(
            f"Port {port} is already in use by container {existing_container}.\n"
            "To remove the existing container, run:\n"
            f"  {stop_command}\n"
            "Then try running this command again."
        )

    # Define the container image and command
    image = "ghcr.io/astral-sh/uv:0.9.25-python3.14-bookworm"
    container_command = ["uvx", "marimo"]
    if debug:
        container_command.append("-d")
    container_command.extend(
        [
            mode,
            "--sandbox",
            "--no-token",
            "-p",
            f"{port}",
            "--host",
            host,
        ]
    )
    if execute_opengraph_generators:
        container_command.append("--execute-opengraph-generators")
    if file_path is not None:
        container_command.append(file_path)

    # Construct the container run command
    run_command = [
        engine,
        "run",
        "--rm",
        "-d",
        "-p",
        f"{port}:{port}",
        "-e",
        "MARIMO_MANAGE_SCRIPT_METADATA=true",
        "-e",
        "MARIMO_IN_SECURE_ENVIRONMENT=true",
        "-w",
        "/home",
        image,
    ] + container_command

    # Run the container
    echo(f"Running command: {muted(' '.join(run_command))}")
    container_id = None
    try:
        result = subprocess.run(
            run_command, check=True, capture_output=True, text=True
        )
        container_id = result.stdout.strip()
        echo(f"Container ID: {muted(container_id)}")
        echo(f"URL: {green(f'http://{host}:{port}')}")

        # Stream logs
        log_command = [engine, "logs", "-f", container_id]
        with subprocess.Popen(
            log_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ) as process:
            try:
                for line in process.stdout or []:
                    echo(line.strip())
            except KeyboardInterrupt:
                echo("Received keyboard interrupt.")
    except subprocess.CalledProcessError as e:
        message = f"Failed to start {engine} container: {e}"
        if e.stderr:
            message += f"\n{e.stderr.strip()}"
        raise MarimoCLIRuntimeError(message) from e
    finally:
        if container_id is not None:
            echo("Stopping and removing container...")
            try:
                subprocess.run(
                    [engine, "stop", container_id],
                    check=True,
                    capture_output=True,
                )
                echo(muted("Container stopped and removed successfully"))
            except subprocess.CalledProcessError:
                echo_red("Failed to stop and remove container")
