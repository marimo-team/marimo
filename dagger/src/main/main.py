from typing import Annotated

import dagger
from dagger import dag, DefaultPath, Doc, function, Ignore, object_type

from .env import Env

@object_type
class Marimo:
    """A collection of tasks for the Marimo project."""

    @function
    def make(
        self,
        src: Annotated[dagger.Directory, Doc("The marimo source tree to use"), DefaultPath("/"), Ignore(["/dagger", ".venv"])],
        task: Annotated[str, Doc("The make task to run")],
    ) -> dagger.Container:
        """A container that runs a make task."""
        return (
            Env().dev().
            with_directory("/src", src).
            with_workdir("/src").
            with_exec(["make", "install-all"]).
            with_exec(["make", task])
        )
