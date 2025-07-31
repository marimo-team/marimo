#!/usr/bin/env python3
import marimo

__generated_with = "0.11.5"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""This marimo notebook generates the OpenAPI schema for the `TypeDict`s defined in `marimo._schemas.session`""")
    return


@app.cell
def _():
    from marimo._schemas.session import (
        TimeMetadata,
        StreamOutput,
        ErrorOutput,
        DataOutput,
        Cell,
        NotebookSessionMetadata,
        NotebookSessionV1,
    )

    MESSAGES = [
        TimeMetadata,
        StreamOutput,
        ErrorOutput,
        DataOutput,
        Cell,
        NotebookSessionMetadata,
        NotebookSessionV1,
    ]
    return (
        Cell,
        DataOutput,
        ErrorOutput,
        MESSAGES,
        NotebookSessionMetadata,
        NotebookSessionV1,
        StreamOutput,
        TimeMetadata,
    )


@app.cell(hide_code=True)
def _(mo):
    generate_schema = mo.ui.run_button(label="Write schema")
    generate_schema
    return (generate_schema,)


@app.cell
def _(build_openapi_schema, generate_schema, mo):
    if generate_schema.value:
        import yaml

        output = mo.notebook_dir() / "session.yaml"
        output.write_text(yaml.dump(build_openapi_schema()))
    return output, yaml


@app.cell(hide_code=True)
def _(Any, Dict, MESSAGES):
    from marimo._server.api.router import build_routes
    from marimo._utils.dataclass_to_openapi import (
        PythonTypeToOpenAPI,
    )


    def build_openapi_schema():
        processed_classes: Dict[Any, str] = {}
        component_schemas: Dict[str, Any] = {}
        name_overrides: Dict[Any, str] = {}

        converter = PythonTypeToOpenAPI(
            camel_case=False, name_overrides=name_overrides
        )
        for cls in MESSAGES:
            if cls in processed_classes:
                del processed_classes[cls]
            name = name_overrides.get(cls, cls.__name__)  # type: ignore[attr-defined]
            component_schemas[name] = converter.convert(cls, processed_classes)
            processed_classes[cls] = name

        schemas = {
            "openapi": "3.0.0",
            "info": {"title": "marimo_session"},
            "components": {
                "schemas": {
                    **component_schemas,
                }
            },
        }
        return schemas
    return PythonTypeToOpenAPI, build_openapi_schema, build_routes


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
