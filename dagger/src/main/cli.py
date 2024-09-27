from typing import Annotated

import dagger
from dagger import dag, DefaultPath, Doc, field, function, Ignore, object_type

@object_type
class Cli:
    src: Annotated[dagger.Directory, Doc("The marimo source tree to use"), DefaultPath("/"), Ignore(["/dagger", ".venv"])] = field()

    @function
    def test(self) -> dagger.Container:
        return (
            # python base
            dag.container().from_("python:3-bookworm")
        )
