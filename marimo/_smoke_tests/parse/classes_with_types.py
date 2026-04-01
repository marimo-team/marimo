import marimo

__generated_with = "0.18.0"
app = marimo.App(width="medium")

with app.setup:
    from typing import TypeAlias

    MySetupTypeAlias: TypeAlias = int
    type MySetupType = int


@app.class_definition
class SetupTypeAlias:
    """Class using a TypeAlias defined in the app setup block."""

    def __init__(self, value: MySetupTypeAlias):
        self.value = value


@app.class_definition
class SetupType:
    """Class using a PEP 695 type alias defined in the app setup block."""

    def __init__(self, value: MySetupType):
        self.value = value


@app.class_definition
class EmbeddedTypeAlias:
    """Class with an embedded TypeAlias class variable."""

    MyEmbeddedTypeAlias: TypeAlias = int

    def __init__(self, value: MyEmbeddedTypeAlias):
        self.value = value


@app.class_definition
class EmbeddedType:
    """Class with an embedded PEP 695 type statement class variable."""

    type MyEmbeddedType = int

    def __init__(self, value: MyEmbeddedType):
        self.value = value


if __name__ == "__main__":
    app.run()
