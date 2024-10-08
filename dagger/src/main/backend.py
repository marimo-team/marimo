from typing import Annotated

import dagger
from dagger import dag, DefaultPath, Doc, field, function, Ignore, object_type

from .env import Env

@object_type
class Backend:
    src: Annotated[dagger.Directory, Doc("The marimo source tree to use")] = field()

    @function
    def test(self) -> dagger.Container:
        return (
            # python base
            Env().py()
            .with_directory("/src", self.src)
            .with_workdir("/src")
            .with_exec(["make", "py"])
            .with_exec(["make", "py-test"])
        )
