# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._cli.containers.engine import LaunchRequest

OWNERSHIP_LABEL = "io.marimo.session"


def create_args(
    request: LaunchRequest, name: str, *, relabel_mounts: bool = False
) -> list[str]:
    args = ["create", "--name", name, "--label", f"{OWNERSHIP_LABEL}={name}"]
    for mapping in request.ports:
        args.extend(("--publish", f"{mapping.host}:{mapping.container}"))
    for key, value in request.environment:
        args.extend(("--env", f"{key}={value}"))
    if request.working_directory is not None:
        args.extend(("--workdir", request.working_directory))
    for mount in request.mounts:
        # Apple container splits --mount fields on commas.
        if "," in mount.source or "," in mount.target:
            options = ["ro"] if mount.read_only else []
            if relabel_mounts:
                options.append("Z")
            volume = f"{mount.source}:{mount.target}"
            if options:
                volume += ":" + ",".join(options)
            args.extend(("--volume", volume))
            continue
        mode = ",readonly" if mount.read_only else ""
        relabel = ",relabel=private" if relabel_mounts else ""
        args.extend(
            (
                "--mount",
                f"type=bind,source={mount.source},target={mount.target}{mode}{relabel}",
            )
        )
    args.extend((request.image, *request.argv))
    return args
