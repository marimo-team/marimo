# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "datamodel-code-generator==0.72.0",
#   "ruff==0.16.4",
#   "msgspec[yaml]==0.22.0"
# ]
# ///
"""Generate msgspec models for the marimo host protocol."""

import argparse
import ast
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


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
        assert annotation.end_lineno is not None
        assert annotation.end_col_offset is not None
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


def generate_models(document: dict[str, Any], output_path: Path) -> None:
    from datamodel_code_generator import (
        DataModelType,
        DatetimeClassType,
        InputFileType,
        PythonVersion,
        generate,
    )

    # Freeze records and keep identifier types distinct without changing their wire shape.
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
            "# Regenerate with `make host-protocol-codegen`.\n"
            "# ruff: noqa: TC003 - msgspec resolves annotations at runtime\n"
            "# ruff: noqa: RUF036 - the generator orders unions; the wire shape is the same"
        ),
    )

    output_path.write_bytes(tuple_arrays(output_path.read_bytes()))

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


def main() -> None:
    import msgspec.yaml

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    destination = root.parents[1] / "marimo" / "_core" / "protocol.py"
    document = sorted_keys(
        msgspec.yaml.decode((root / "openapi.yaml").read_bytes())
    )
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "protocol.py"
        generate_models(document, output)
        content = output.read_bytes()
        if not destination.exists() or destination.read_bytes() != content:
            if args.check:
                raise SystemExit(
                    "Host models are stale; run make host-protocol-codegen"
                )
            destination.write_bytes(content)
    print("Host protocol models are current.")


if __name__ == "__main__":
    main()
