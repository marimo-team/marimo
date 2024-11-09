# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
from typing import Optional

import click
from click import echo

from marimo import _loggers
from marimo._cli.print import green, muted, red
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._utils.url import is_url

LOGGER = _loggers.marimo_logger()


def prompt_run_in_docker_container(name: str | None) -> bool:
    if GLOBAL_SETTINGS.IN_SECURE_ENVIRONMENT:
        return False
    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        return False

    # Only prompt for remote files
    if name is None:
        return False
    if not is_url(name):
        return False

    if GLOBAL_SETTINGS.YES:
        return True

    # Check if not in an interactive terminal
    # default to False
    if not sys.stdin.isatty():
        return False

    return click.confirm(
        "This notebook is hosted on a remote server.\n"
        + green(
            "Would you like to run it in a secure docker container?",
            bold=True,
        ),
        default=True,
    )


def _check_docker_installed() -> bool:
    try:
        subprocess.run(
            ["docker", "--version"], check=True, capture_output=True, text=True
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False


def _check_docker_running() -> bool:
    try:
        subprocess.run(
            ["docker", "info"], check=True, capture_output=True, text=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def echo_red(text: str) -> None:
    echo(red(text))


# Run a marimo file in a docker container
# marimo edit https://github.com/some/file.py --docker
def _check_port_in_use(port: int) -> Optional[str]:
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}\t{{.Ports}}", "--no-trunc"],
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
    file_path: str,
    *,
    port: Optional[int],
    debug: bool = False,
) -> None:
    echo(f"Starting {green('containerized')} marimo notebook")

    host = "0.0.0.0"
    if port is None:
        port = 8080

    if not _check_docker_installed():
        echo_red(
            "Docker is not installed. Please install Docker and try again."
        )
        sys.exit(1)

    if not _check_docker_running():
        echo_red(
            "Docker daemon is not running. Please start Docker and try again."
        )
        sys.exit(1)

    # Check if the port is already in use
    existing_container = _check_port_in_use(port)
    if existing_container:
        echo_red(
            f"Port {port} is already in use by container {existing_container}"
        )
        echo("To remove the existing container, run:")
        echo(muted(f"  docker stop {existing_container}"))
        echo("Then try running this command again.")
        sys.exit(1)

    # Define the container image and command
    image = "ghcr.io/astral-sh/uv:0.4.21-python3.12-bookworm"
    container_command = [
        "uvx",
        "marimo",
        "-d" if debug else "",
        "edit",
        "--sandbox",
        "--no-token",
        "-p",
        f"{port}",
        "--host",
        host,
        file_path,
    ]
    # Remove empty strings from command
    container_command = [arg for arg in container_command if arg]

    # Construct the docker run command
    docker_command = [
        "docker",
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
        "/app",
        image,
    ] + container_command

    # Run the container
    echo(f"Running command: {muted(' '.join(docker_command))}")
    container_id = None
    try:
        result = subprocess.run(
            docker_command, check=True, capture_output=True, text=True
        )
        container_id = result.stdout.strip()
        echo(f"Container ID: {muted(container_id)}")
        echo(f"URL: {green(f'http://{host}:{port}')}")

        # Stream logs
        log_command = ["docker", "logs", "-f", container_id]
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
        echo_red(f"Failed to start Docker container: {e}")
        sys.exit(1)
    finally:
        echo("Stopping and removing container...")
        try:
            if container_id is not None:
                subprocess.run(
                    ["docker", "stop", container_id],
                    check=True,
                    capture_output=True,
                )
            echo(muted("Container stopped and removed successfully"))
        except subprocess.CalledProcessError:
            echo_red("Failed to stop and remove container")
