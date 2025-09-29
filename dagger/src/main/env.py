import dagger
from dagger import dag, function, object_type


@object_type
class Env:
    @function
    def dev(self) -> dagger.Container:
        """Dev container with dependencies for the full stack"""
        return (
            # python base
            self.py()
            .with_mounted_cache(
                "/root/.local/share/pnpm", dag.cache_volume("pnpm")
            )
            # package deps
            .with_exec(["apt", "update"])
            .with_exec(["apt", "install", "-y", "curl"])
            # install node 20+
            .with_exec(
                [
                    "sh",
                    "-c",
                    "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",  # noqa: E501
                ]
            )
            .with_exec(["apt", "install", "-y", "nodejs"])
            # install pnpm@9
            .with_exec(["npm", "install", "-g", "pnpm@9"])
        )

    @function
    def py(self) -> dagger.Container:
        """Python container with dependencies for the backend"""
        return (
            # python base
            dag.container()
            .from_("python:3.12-bookworm")
            .with_exec(["apt-get", "update"])
            .with_exec(
                [
                    "apt-get",
                    "install",
                    "-y",
                    "make",
                    "libgdal-dev",
                    "python3-gdal",
                ]
            )
            .with_exec(["adduser", "nonroot"])
            .with_mounted_cache(
                "/home/nonroot/.cache/pip",
                dag.cache_volume("python-312"),
                owner="nonroot",
            )
            .with_mounted_cache(
                "/home/nonroot/.cache/uv",
                dag.cache_volume("uv-python-312"),
                owner="nonroot",
            )
            .with_exec(["pip", "install", "hatch", "typos"])
            .with_user("nonroot")
        )

    @function
    def pnpm(self) -> dagger.Container:
        """A pnpm container with dependencies for the frontend"""
        return (
            dag.container()
            .from_("node:20-slim")
            .with_env_variable("CI", "true")
            .with_mounted_cache(
                "/root/.local/share/pnpm", dag.cache_volume("pnpm")
            )
            .with_exec(["corepack", "enable"])  # this enables pnpm
        )
