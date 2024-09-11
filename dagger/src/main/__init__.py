"""A module for Marimo functions
"""
from typing import Annotated

import dagger
from dagger import DefaultPath, dag, function, object_type

@object_type
class Marimo:
    @function
    def make(
        self,
        src: Annotated[dagger.Directory, DefaultPath("/")],
        task: str
    ) -> dagger.Container:
        return (
            dev_env(dag).
            with_directory("/src", src).
            with_workdir("/src").
            with_exec(["make", "install-all"]).
            with_exec(["make", task])
        )

def dev_env(dag: dagger.Client) -> dagger.Container:
    return (
        # python base
        dag.container().from_("python:3-bookworm").
        # package deps
        with_exec(["apt", "update"]).
        with_exec(["apt", "install", "-y", "curl", "make"]).
        # install node 20+
        with_exec(["sh", "-c", "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"]).
        with_exec(["apt", "install", "-y", "nodejs"]).
        # install pnpm@8
        with_exec(["npm", "install", "-g", "pnpm@8"]).
        with_env_variable("NODE_OPTIONS", "--max-old-space-size=4096")
    )
