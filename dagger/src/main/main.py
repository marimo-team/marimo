from typing import Annotated

import dagger
from dagger import dag, DefaultPath, Doc, field, function, Ignore, object_type

from .env import Env
from .backend import Backend
from .frontend import Frontend
from .cli import Cli

@object_type
class Marimo:
    """A collection of tasks for the Marimo project."""
    src: Annotated[dagger.Directory, Doc("The marimo source tree to use")] = field()
    frontend: Annotated[Frontend, Doc("Frontend components")] = field()
    backend: Annotated[Backend, Doc("Backend components")] = field()
    cli: Annotated[Cli, Doc("CLI components")] = field()
    env: Annotated[Env, Doc("Test and Build environments")] = field()

    @classmethod
    def create(
        cls,
        src: Annotated[dagger.Directory, Doc("The marimo source tree to use"), DefaultPath("/"), Ignore(["**/dagger", "**/.venv"])],
    ):
        return cls(
            src=src,
            frontend=Frontend(src=src),
            backend=Backend(src=src),
            cli=Cli(src=src),
            env=Env()
        )

    @function
    def make(
        self,
        task: Annotated[str, Doc("The make task to run")],
    ) -> dagger.Container:
        """A container that runs a make task."""
        return (
            self.env.dev().
            with_directory("/src", self.src).
            with_workdir("/src").
            with_exec(["make", "install-all"]).
            with_exec(["make", task])
        )