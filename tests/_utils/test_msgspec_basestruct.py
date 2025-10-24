import typing as t

import msgspec

from marimo._ai._tools.tools.cells import (
    GetCellRuntimeDataArgs,
    GetCellRuntimeDataOutput,
    GetLightweightCellMapArgs,
    GetLightweightCellMapOutput,
    GetCellOutputArgs,
    GetCellOutputOutput,
)
from marimo._ai._tools.tools.datasource import (
    GetDatabaseTablesArgs,
    GetDatabaseTablesOutput,
)
from marimo._ai._tools.tools.errors import (
    GetNotebookErrorsArgs,
    GetNotebookErrorsOutput,
)
from marimo._ai._tools.tools.notebooks import (
    GetActiveNotebooksOutput,
)
from marimo._ai._tools.tools.tables_and_variables import (
    TablesAndVariablesArgs,
    TablesAndVariablesOutput,
)
from marimo._ai._tools.tools.lint import (
    LintNotebookArgs,
    LintNotebookOutput,
)

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
