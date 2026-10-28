# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "datamodel-code-generator==0.72.0",
#   "jinja2==3.1.6",
#   "ruff==0.16.4",
#   "msgspec[yaml]==0.22.0",
#   "python-jsonpath==2.2.1"
# ]
# ///
"""Compose the host contract and generate its Python bindings or OpenAPI JSON."""

import argparse
import ast
import copy
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import jsonpath
import msgspec.yaml

ROOT = Path(__file__).resolve().parent


def merge(target: dict[str, Any], update: dict[str, Any]) -> None:
    """Recursively merge object properties, replacing other values."""
    for key, value in update.items():
        if isinstance(target.get(key), dict) and isinstance(value, dict):
            merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def compose(
    selection: str | None = None, *, root: Path = ROOT
) -> dict[str, Any]:
    document = msgspec.yaml.decode((root / "openapi.yaml").read_bytes())
    available = {
        path.parent.name: path
        for path in (root / "experimental").glob("*/overlay.yaml")
    }
    if selection is None:
        selected = []
    elif selection == "all":
        selected = sorted(available)
    else:
        selected = sorted(set(selection.split(",")))
    unknown = set(selected) - available.keys()
    if unknown:
        raise ValueError(
            f"Unknown experimental features: {', '.join(sorted(unknown))}"
        )
    for name in selected:
        overlay = msgspec.yaml.decode(available[name].read_bytes())
        if overlay["overlay"] != "1.0.0":
            raise ValueError("Only OpenAPI Overlay 1.0.0 is supported")
        schemas = document["components"]["schemas"]
        previous = set(schemas)
        for action in overlay["actions"]:
            if action.get("remove"):
                raise ValueError("Experimental overlays support updates only")
            matches = jsonpath.findall(action["target"], document, strict=True)
            if not matches:
                raise ValueError(
                    f"Overlay target does not exist: {action['target']}"
                )
            for target in matches:
                update = action["update"]
                if isinstance(target, dict) and isinstance(update, dict):
                    merge(target, update)
                elif isinstance(target, list):
                    target.append(copy.deepcopy(update))
                else:
                    raise ValueError(
                        f"Expected an object or array: {action['target']}"
                    )
        for schema in schemas.keys() - previous:
            schemas[schema]["description"] = (
                f"Experimental ({name}). "
                + schemas[schema].get("description", "")
            )
    if selected:
        document["x-marimo-experimental"] = selected
    return document


# msgspec decodes tuple fields from JSON arrays without changing the wire format.
class TupleArrays(ast.NodeTransformer):
    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == "list":
            node.value.id = "tuple"
            node.slice = ast.Tuple(
                elts=[node.slice, ast.Constant(value=Ellipsis)]
            )
        return node


def sorted_keys(value: Any) -> Any:
    """Keep model and field ordering independent of the YAML layout."""
    if isinstance(value, dict):
        return {key: sorted_keys(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [sorted_keys(item) for item in value]
    return value


def tuple_arrays(source: bytes) -> bytes:
    """Rewrite array annotations using the AST's UTF-8 byte offsets."""
    lines = source.splitlines(keepends=True)
    # Rewrite annotations only, preserving the generated header and layout.
    for node in sorted(
        (
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.AnnAssign)
        ),
        key=lambda node: (node.lineno, node.col_offset),
        reverse=True,
    ):
        annotation = node.annotation
        if not any(
            isinstance(child, ast.Subscript)
            and isinstance(child.value, ast.Name)
            and child.value.id == "list"
            for child in ast.walk(annotation)
        ):
            continue
        if annotation.end_lineno is None:
            raise RuntimeError("Annotation has no end line")
        if annotation.end_col_offset is None:
            raise RuntimeError("Annotation has no end column")
        start = (
            sum(map(len, lines[: annotation.lineno - 1]))
            + annotation.col_offset
        )
        end = (
            sum(map(len, lines[: annotation.end_lineno - 1]))
            + annotation.end_col_offset
        )
        replacement = ast.unparse(TupleArrays().visit(annotation)).encode(
            "utf-8"
        )
        source = source[:start] + replacement + source[end:]
    return source


def regeneration_command(document: dict[str, Any]) -> str:
    features = document.get("x-marimo-experimental", [])
    command = "uv run --no-config --locked --script protocols/host/generate.py"
    return command + (
        f" --include-experimental={','.join(features)}" if features else ""
    )


def event_adapters(
    document: dict[str, Any], *, relative_import: bool = False
) -> str:
    """Derive typed event adapters from the discriminator and schema refs."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    schemas = document["components"]["schemas"]
    mapping = schemas["Event"]["discriminator"]["mapping"]

    def reference(value: dict[str, Any]) -> str:
        ref = value["$ref"]
        prefix = "#/components/schemas/"
        if not ref.startswith(prefix):
            raise ValueError(f"Expected a local schema reference: {ref}")
        return ref.removeprefix(prefix)

    records = {}
    removals = []
    for tag, ref in sorted(mapping.items()):
        name = reference({"$ref": ref})
        data = schemas[name]["properties"]["data"]
        if "$ref" not in data:
            continue  # Control events have no record payload.
        message = reference(data)
        if tag.endswith(".removed"):
            removals.append((tag.removesuffix(".removed"), name, message))
            continue
        schema = schemas[message]
        fields = {
            field: reference(value)
            for field, value in schema["properties"].items()
            if "$ref" in value
            and schemas[reference(value)].get("type") == "object"
            and field in schema.get("required", [])
        }
        if len(fields) != 1:
            raise ValueError(f"{message} must contain one required record")
        field, body = next(iter(fields.items()))
        if set(schema["properties"]) != {field, "request_id", "time"}:
            raise ValueError(f"Unsupported event metadata in {message}")
        records[tag] = {
            "event": name,
            "message": message,
            "body": body,
            "field": field,
            "requires_time": "time" in schema.get("required", []),
        }

    removed = []
    for tag, name, message in removals:
        if tag not in records:
            raise ValueError(f"{name} has no corresponding record event")
        removed.append({**records[tag], "event": name, "message": message})

    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return env.get_template("events.py.jinja2").render(
        records=list(records.values()),
        removals=removed,
        command=regeneration_command(document),
        features=document.get("x-marimo-experimental", []),
        relative_import=relative_import,
    )


def format_generated(output_path: Path) -> None:
    subprocess.run(
        [
            "ruff",
            "format",
            "--isolated",
            "--line-length",
            "79",
            str(output_path),
        ],
        check=True,
    )


def generate_models(document: dict[str, Any], output_path: Path) -> None:
    from datamodel_code_generator import (
        DataModelType,
        DatetimeClassType,
        InputFileType,
        PythonVersion,
        generate,
    )

    # Freeze records and keep identifier types distinct without changing their wire shape.
    features = document.get("x-marimo-experimental", [])
    experimental_header = (
        f"# Experimental features: {', '.join(features)}\n" if features else ""
    )
    schemas = document["components"]["schemas"]
    template_data = defaultdict(dict)
    for name, schema in schemas.items():
        template_data[name]["base_class_kwargs"] = {"frozen": "True"}
        if name.endswith("Id") and schema.get("type") == "string":
            template_data[name]["newtype"] = True

    generate(
        input_=document,
        input_file_type=InputFileType.OpenAPI,
        output=output_path,
        output_model_type=DataModelType.MsgspecStruct,
        target_python_version=PythonVersion.PY_310,
        disable_timestamp=True,
        use_union_operator=True,
        use_standard_collections=True,
        use_standard_primitive_types=True,
        output_datetime_class=DatetimeClassType.Datetime,
        enum_field_as_literal="all",
        strict_nullable=True,
        field_constraints=True,
        use_annotated=True,
        custom_template_dir=Path(__file__).parent / "templates",
        extra_template_data=template_data,
        additional_imports=["typing.TYPE_CHECKING", "typing.NewType"],
        formatters=["builtin"],
        custom_file_header=(
            "# Copyright 2026 Marimo. All rights reserved.\n"
            "# AUTO-GENERATED FILE — DO NOT EDIT.\n"
            "# Generated from protocols/host/openapi.yaml.\n"
            + experimental_header
            + f"# Regenerate with `{regeneration_command(document)}`.\n"
            "# ruff: noqa: TC003 - msgspec resolves annotations at runtime\n"
            "# ruff: noqa: RUF036 - the generator orders unions; the wire shape is the same"
        ),
    )

    output_path.write_bytes(tuple_arrays(output_path.read_bytes()))

    format_generated(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument(
        "--schema",
        action="store_true",
        help="Print the composed OpenAPI document as JSON instead of generating bindings",
    )
    parser.add_argument(
        "--include-experimental",
        nargs="?",
        const="all",
        help="Include all experimental features, or a comma-separated selection",
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    default_destination = ROOT.parents[1] / "marimo" / "_core"
    destination = args.output_dir or default_destination
    document = compose(args.include_experimental)
    if args.schema:
        sys.stdout.write(json.dumps(document) + "\n")
        return
    document = sorted_keys(document)
    if not args.check:
        destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "protocol.py"
        generate_models(document, output)
        adapters = Path(directory) / "protocol_events.py"
        adapters.write_text(
            event_adapters(
                document,
                relative_import=destination.resolve() != default_destination,
            ),
            encoding="utf-8",
        )
        format_generated(adapters)
        for generated in (output, adapters):
            target = destination / generated.name
            content = generated.read_bytes()
            if not target.exists() or target.read_bytes() != content:
                if args.check:
                    raise SystemExit(
                        "Host bindings are stale; regenerate with the same "
                        "feature selection and output directory"
                    )
                target.write_bytes(content)
    print("Host protocol models are current.")


if __name__ == "__main__":
    main()
