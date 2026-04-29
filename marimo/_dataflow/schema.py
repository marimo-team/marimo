# Copyright 2026 Marimo. All rights reserved.
"""Dataflow schema introspection.

The schema is **kernel-derived**: we run the notebook once with default UI
element values and walk the resulting `mo.api.input(...)` UI elements to
build the input list. Outputs and triggers come from static graph analysis
plus annotation hints. The schema is then cached on the file's content hash.

This means:

- Dynamic constraints work (e.g. dropdown options computed from a dataframe).
- The schema is deterministic: same notebook code → same schema.
- A first request pays a cold-start cost; subsequent requests hit the cache.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import msgspec

from marimo._ast.variables import is_local, is_mangled_local
from marimo._dataflow.api import (
    DATAFLOW_INPUT_MARKER,
    _InputMetadata,
    _OutputAnnotation,
    _TriggerAnnotation,
)
from marimo._dataflow.protocol import (
    DataflowSchema,
    InputSchema,
    Kind,
    OutputSchema,
    TriggerSchema,
)
from marimo._dataflow.serialize import infer_kind

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp
    from marimo._dataflow.runtime import DataflowRuntime


def _kind_for_ui_element(element: Any) -> Kind:
    """Infer a `Kind` from a `mo.ui.*` element instance.

    For inputs we report the kind of the *value* the element produces, not
    the kind of the element itself, so clients can validate overrides.
    """
    try:
        value = element.value
    except Exception:
        value = None
    return infer_kind(value)


def _input_schema_from_element(name: str, element: Any) -> InputSchema:
    """Build an InputSchema from a `mo.api.input(...)` UI element."""
    metadata: _InputMetadata = getattr(element, DATAFLOW_INPUT_MARKER)
    try:
        default = element.value
    except Exception:
        default = None

    kind = (
        Kind(metadata.kind_hint)
        if metadata.kind_hint
        else _kind_for_ui_element(element)
    )

    constraints = dict(metadata.constraints) if metadata.constraints else {}
    ui_type = type(element).__name__
    constraints["ui"] = ui_type

    return InputSchema(
        name=name,
        kind=kind,
        default=default,
        description=metadata.description,
        required=False,
        constraints=constraints or None,
    )


def _free_var_input_schema(name: str, value: Any) -> InputSchema:
    """Fallback for inputs detected as free variables (no `mo.api.input`)."""
    return InputSchema(name=name, kind=infer_kind(value))


def _collect_outputs_and_triggers(
    app: InternalApp,
) -> tuple[set[str], list[str]]:
    """Walk the graph, collect public defs and side-effect cell names."""
    graph = app.graph
    all_defs: set[str] = set()
    trigger_cells: list[str] = []

    for cell_id in app.execution_order:
        cell = graph.cells.get(cell_id)
        if cell is None or graph.is_disabled(cell_id):
            continue

        cell_defs = {
            d for d in cell.defs if not is_local(d) and not is_mangled_local(d)
        }
        cell_refs = {
            r for r in cell.refs if not is_local(r) and not is_mangled_local(r)
        }
        all_defs.update(cell_defs)
        if not cell_defs and cell_refs:
            cell_name = (
                cell.config.name
                if hasattr(cell.config, "name") and cell.config.name
                else None
            )
            if cell_name:
                trigger_cells.append(cell_name)
    return all_defs, trigger_cells


def _trigger_annotations(
    globals_: dict[str, Any],
) -> dict[str, _TriggerAnnotation]:
    """Find `@mo.api.trigger`-decorated callables in globals."""
    out: dict[str, _TriggerAnnotation] = {}
    for name, val in globals_.items():
        if callable(val) and hasattr(val, "__dataflow_annotations__"):
            for ann in val.__dataflow_annotations__:
                if isinstance(ann, _TriggerAnnotation):
                    out[name] = ann
    return out


def _output_annotations(
    globals_: dict[str, Any],
) -> dict[str, _OutputAnnotation]:
    """Find `Annotated[T, mo.api.output(...)]` annotations in globals."""
    import typing

    annotations = globals_.get("__annotations__", {})
    out: dict[str, _OutputAnnotation] = {}
    for name, ann in annotations.items():
        if typing.get_origin(ann) is getattr(typing, "Annotated", None):
            for arg in typing.get_args(ann)[1:]:
                if isinstance(arg, _OutputAnnotation):
                    out[name] = arg
    return out


def compute_dataflow_schema(runtime: DataflowRuntime) -> DataflowSchema:
    """Compute the dataflow schema by introspecting an initialized runtime.

    Must be called on the runtime's worker thread (where the script context
    is installed). `DataflowFileBundle.get_schema` handles thread routing.
    """
    runtime._initialize_blocking()
    app = runtime._app
    glbls = runtime.globals

    input_elements = runtime.list_input_elements()
    inputs: list[InputSchema] = sorted(
        (
            _input_schema_from_element(name, element)
            for name, element in input_elements.items()
        ),
        key=lambda s: s.name,
    )

    if not inputs:
        # Fallback for notebooks that don't use `mo.api.input` yet: detect
        # free variables. Useful while migrating.
        graph = app.graph
        all_refs: set[str] = set()
        for cell_id in app.execution_order:
            cell = graph.cells.get(cell_id)
            if cell is None or graph.is_disabled(cell_id):
                continue
            all_refs.update(
                r
                for r in cell.refs
                if not is_local(r) and not is_mangled_local(r)
            )
        defined = set(graph.definitions.keys())
        import builtins

        builtin_names = set(dir(builtins))
        free_vars = {
            v
            for v in all_refs - defined
            if not v.startswith("__") and v not in builtin_names
        }
        inputs = sorted(
            (
                _free_var_input_schema(name, glbls.get(name))
                for name in free_vars
            ),
            key=lambda s: s.name,
        )

    all_defs, trigger_cells = _collect_outputs_and_triggers(app)
    output_anns = _output_annotations(glbls)
    trigger_anns = _trigger_annotations(glbls)

    import types as _types

    input_names = {i.name for i in inputs}
    outputs: list[OutputSchema] = []
    for name in sorted(all_defs):
        if name in input_names:
            continue
        value = glbls.get(name)
        # Modules in cell defs are typically imports — never useful as
        # dataflow outputs and just clutter the schema.
        if isinstance(value, _types.ModuleType):
            continue
        kind = infer_kind(value)
        ann = output_anns.get(name)
        if ann:
            outputs.append(
                OutputSchema(
                    name=name,
                    kind=Kind(ann.kind) if ann.kind else kind,
                    description=ann.description,
                    accepts=ann.accepts,
                )
            )
        else:
            outputs.append(OutputSchema(name=name, kind=kind))

    trigger_names = sorted(set(trigger_cells) | set(trigger_anns.keys()))
    triggers: list[TriggerSchema] = [
        TriggerSchema(
            name=name,
            description=(
                trigger_anns[name].description
                if name in trigger_anns
                else None
            ),
        )
        for name in trigger_names
    ]

    schema_bytes = msgspec.json.encode(
        {
            "inputs": [i.name for i in inputs],
            "outputs": [o.name for o in outputs],
            "triggers": [t.name for t in triggers],
        }
    )
    schema_id = hashlib.sha256(schema_bytes).hexdigest()[:16]

    return DataflowSchema(
        inputs=inputs,
        outputs=outputs,
        triggers=triggers,
        schema_id=schema_id,
    )
