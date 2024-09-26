import dagger
from dagger import dag, function, object_type

@object_type
class Cli:
    @function
    def test(self) -> dagger.Container:
        return (
            # python base
            dag.container().from_("python:3-bookworm")
        )
