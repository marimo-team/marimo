# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._cli.containers.engine import LaunchRequest

OWNERSHIP_LABEL = "io.marimo.session"


def create_args(request: LaunchRequest, name: str) -> list[str]:
    args = ["create", "--name", name, "--label", f"{OWNERSHIP_LABEL}={name}"]
    for mapping in request.ports:
        args.extend(("--publish", f"{mapping.host}:{mapping.container}"))
    for key, value in request.environment:
        args.extend(("--env", f"{key}={value}"))
    if request.working_directory is not None:
        args.extend(("--workdir", request.working_directory))
    for mount in request.mounts:
        mode = ",readonly" if mount.read_only else ""
        args.extend(
            (
                "--mount",
                f"type=bind,source={mount.source},target={mount.target}{mode}",
            )
        )
    args.extend((request.image, *request.argv))
    return args
