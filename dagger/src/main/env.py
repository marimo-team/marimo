import dagger
from dagger import DefaultPath, dag, function, object_type

@object_type
class Env:
    @function
    def dev(self) -> dagger.Container:
        """Dev container with dependencies for the full stack"""
        return (
            # python base
            dag.container().from_("python:3-bookworm")
            # package deps
            .with_exec(["apt", "update"])
            .with_exec(["apt", "install", "-y", "curl", "make"])
            # install node 20+
            .with_exec(["sh", "-c", "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"])
            .with_exec(["apt", "install", "-y", "nodejs"])
            # install pnpm@8
            .with_exec(["npm", "install", "-g", "pnpm@8"])
            .with_env_variable("NODE_OPTIONS", "--max-old-space-size=8192")
        )

    @function
    def pnpm(self) -> dagger.Container:
        """pnpm container with dependencies for the frontend"""
        return (
            dag.container().from_("node:20-slim")
            .with_env_variable("CI", "true")
            .with_env_variable("NODE_OPTIONS", "--max-old-space-size=8192")
            .with_exec(["corepack", "enable"]) # this enables pnpm
        )
