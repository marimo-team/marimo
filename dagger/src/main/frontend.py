from typing import Annotated

import dagger
from dagger import Doc, dag, field, function, object_type

from .env import Env


@object_type
class Frontend:
    src: Annotated[dagger.Directory, Doc("The marimo source tree to use")] = (
        field()
    )

    @function
    def test(
        self,
        turbo_token: dagger.Secret = dag.set_secret("DEFAULT", ""),  # noqa: B008
    ) -> dagger.Container:
        """
        Replace .github/workflows/test_fe.yaml
        """
        return (
            Env()
            .pnpm()
            .with_env_variable("MARIMO_SKIP_UPDATE_CHECK", "true")
            .with_secret_variable("TURBO_TOKEN", turbo_token)
            .with_env_variable("TURBO_TEAM", "marimo")
            .with_workdir("/src/frontend")
            .with_directory("/src", self.src)
            .with_exec(["pnpm", "install"])
            .with_exec(["pnpm", "dedupe", "--check"])
            .with_exec(["pnpm", "turbo", "lint"])
            .with_exec(["pnpm", "turbo", "typecheck"])
            .with_exec(["pnpm", "test"])
            .with_env_variable("NODE_ENV", "production")
            .with_exec(["pnpm", "turbo", "build"])
            .with_env_variable("VITE_MARIMO_ISLANDS", "true")
            .with_env_variable("VITE_MARIMO_VERSION", "0.0.0")
            .with_exec(["npm", "version", "0.0.0", "--no-git-tag-version"])
            .with_exec(["pnpm", "turbo", "build:islands"])
            .with_exec(["./islands/validate.sh"])
        )
