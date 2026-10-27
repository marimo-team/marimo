import json
import typing as t

import msgspec
import pytest
from pydantic import TypeAdapter, ValidationError

from marimo._ai._tools.tools.cells import (
    GetCellOutputArgs,
    GetCellOutputOutput,
    GetCellRuntimeDataArgs,
    GetCellRuntimeDataOutput,
    GetLightweightCellMapArgs,
    GetLightweightCellMapOutput,
)
from marimo._ai._tools.tools.datasource import (
    GetDatabaseTablesArgs,
    GetDatabaseTablesOutput,
)
from marimo._ai._tools.tools.dependency_graph import (
    GetCellDependencyGraphArgs,
    GetCellDependencyGraphOutput,
)
from marimo._ai._tools.tools.errors import (
    GetNotebookErrorsArgs,
    GetNotebookErrorsOutput,
)
from marimo._ai._tools.tools.lint import (
    LintNotebookArgs,
    LintNotebookOutput,
)
from marimo._ai._tools.tools.notebooks import (
    GetActiveNotebooksOutput,
)
from marimo._ai._tools.tools.tables_and_variables import (
    TablesAndVariablesArgs,
    TablesAndVariablesOutput,
)
from marimo._core.protocol import ExecutionId, Revision
from marimo._messaging.notification import VariableValue

TOOL_IO_CLASSES = [
    GetCellRuntimeDataArgs,
    GetCellRuntimeDataOutput,
    GetLightweightCellMapArgs,
    GetLightweightCellMapOutput,
    TablesAndVariablesArgs,
    TablesAndVariablesOutput,
    GetDatabaseTablesArgs,
    GetDatabaseTablesOutput,
    GetNotebookErrorsArgs,
    GetNotebookErrorsOutput,
    GetActiveNotebooksOutput,
    LintNotebookArgs,
    LintNotebookOutput,
    GetCellOutputArgs,
    GetCellOutputOutput,
    GetCellDependencyGraphArgs,
    GetCellDependencyGraphOutput,
]


def _iter_types(ann: t.Any):
    stack = [ann]
    seen: set[int] = set()
    while stack:
        tp = stack.pop()
        obj_id = id(tp)
        if obj_id in seen:
            continue
        seen.add(obj_id)

        if isinstance(tp, type):
            yield tp
            # Recurse into dataclass-like classes by following their annotations
            anns = getattr(tp, "__annotations__", None)
            if anns:
                stack.extend(anns.values())
            continue

        origin = t.get_origin(tp)
        if origin is not None:
            stack.append(origin)
            stack.extend(t.get_args(tp))


def test_tool_msgspec_structs_expose_pydantic_hook() -> None:
    offenders: list[str] = []
    for cls in TOOL_IO_CLASSES:
        for ann in (getattr(cls, "__annotations__", {}) or {}).values():
            for resolved_type in _iter_types(ann):
                if isinstance(resolved_type, type) and issubclass(
                    resolved_type, msgspec.Struct
                ):
                    if not callable(
                        getattr(
                            resolved_type, "__get_pydantic_core_schema__", None
                        )
                    ):
                        offenders.append(
                            f"{resolved_type.__module__}.{resolved_type.__name__} (referenced by {cls.__module__}.{cls.__name__})"
                        )

    assert not offenders, (
        "These msgspec.Structs referenced by tools must use BaseStruct as their base class: "
        + ", ".join(offenders)
    )


@pytest.mark.parametrize("tool_io_class", TOOL_IO_CLASSES)
def test_tool_io_exposes_pydantic_schema(tool_io_class: type) -> None:
    TypeAdapter(tool_io_class).json_schema()


def test_variable_value_revision_round_trip() -> None:
    adapter = TypeAdapter(VariableValue)
    value = VariableValue(
        name="x",
        value="1",
        datatype="int",
        execution_id="execution-1",
        revision=Revision(execution=ExecutionId("execution-1"), update=2),
    )
    expected = {
        "name": "x",
        "value": "1",
        "datatype": "int",
        "execution_id": "execution-1",
        "revision": {"execution": "execution-1", "update": 2},
    }

    assert adapter.validate_python(value) is value
    assert adapter.validate_json(json.dumps(expected)) == value
    assert adapter.dump_python(value, mode="json") == expected
    assert json.loads(adapter.dump_json(value)) == expected

    invalid = {
        **expected,
        "revision": {"execution": "execution-1", "update": -1},
    }
    with pytest.raises(ValidationError, match="Expected `int` >= 0"):
        adapter.validate_json(json.dumps(invalid))
