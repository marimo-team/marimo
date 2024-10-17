from typing import Annotated

import dagger
from dagger import Doc, field, function, object_type

from .env import Env


@object_type
class Backend:
    src: Annotated[dagger.Directory, Doc("The marimo source tree to use")] = (
        field()
    )

    @function
    async def test(self) -> dagger.Container:
        env = (
            Env()
            .py()
            .with_directory("/src", self.src, owner="nonroot")
            .with_workdir("/src")
            # from GHA: This step is needed since some of our tests rely on the index.html file
            .with_exec(["mkdir", "-p", "marimo/_static/assets"])
            .with_exec(
                ["cp", "frontend/index.html", "marimo/_static/index.html"]
            )
            .with_exec(
                [
                    "cp",
                    "frontend/public/favicon.ico",
                    "marimo/_static/favicon.ico",
                ]
            )
            .with_exec(["make", "py"])
            .with_exec(["hatch", "run", "lint"])
            .with_exec(["hatch", "run", "typecheck:check"])
        )

        await env.sync()

        # test:test
        await env.with_exec(
            [
                "hatch",
                "run",
                "+py=3.12",
                "test:test",
                "-v",
                "tests/",
                "-k",
                "not test_cli",
            ]
        ).sync()

        # test-optional:test
        return env.with_exec(
            [
                "hatch",
                "run",
                "+py=3.12",
                "test-optional:test",
                "-v",
                "tests/",
                "-k",
                "not test_cli",
            ]
        )
