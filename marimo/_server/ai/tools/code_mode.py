# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import copy
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

from marimo._ai._tools.types import CodeExecutionResult
from marimo._server.ai.skills.utils import load_reference
from marimo._server.api.deps import AppState
from marimo._server.api.utils import get_code_mode_credentials
from marimo._server.scratchpad import run_scratchpad_code

if TYPE_CHECKING:
    from pydantic_ai import FunctionToolset
    from pydantic_ai.capabilities import Capability
    from starlette.requests import Request

    from marimo._session.session import Session


ToolStrategy = Literal["code_mode", "hybrid_balanced"]
TOOL_STRATEGY_HEADER = "Marimo-AI-Tool-Strategy"


@dataclass(frozen=True)
class NotebookCellReplacement:
    """Complete source replacement for one existing cell."""

    code: str
    cell_id: str


@dataclass(frozen=True)
class NotebookCellInsertion:
    """One new anonymous cell in an atomic notebook patch."""

    code: str
    after_cell_id: str | None = None


@dataclass(frozen=True)
class NotebookCellConfiguration:
    """Configuration and optional placement for an existing cell."""

    cell_id: str
    hide_code: bool | None = None
    disabled: bool | None = None
    expand_output: bool | None = None
    column: int | None = None
    move_before_cell_id: str | None = None
    move_after_cell_id: str | None = None


def get_tool_strategy(request: Request) -> ToolStrategy:
    """Return the requested experimental code-mode tool strategy."""
    strategy = request.headers.get(TOOL_STRATEGY_HEADER)
    if strategy == "hybrid_balanced":
        return "hybrid_balanced"
    return "code_mode"


def _python_literal(value: object) -> str:
    """Serialize JSON-like tool arguments as a safe Python literal."""
    return repr(value)


def _imports_code_mode(code: str) -> bool:
    """Return whether code imports the private notebook mutation API."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "marimo._code_mode" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module == "marimo._code_mode":
                return True
            if node.module == "marimo" and any(
                alias.name == "_code_mode" for alias in node.names
            ):
                return True
    return False


def compact_hybrid_history(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compact obsolete notebook snapshots in completed chat turns.

    The latest assistant turn stays intact. Older successful inspections can
    be recreated from the live notebook, and older patch source is superseded
    by the notebook state. Exploration results and every error stay verbatim.
    """
    assistant_indexes = [
        index
        for index, message in enumerate(messages)
        if message.get("role") == "assistant"
    ]
    if len(assistant_indexes) < 2:
        return messages

    compacted = copy.deepcopy(messages)
    for message in compacted[: assistant_indexes[-1]]:
        if message.get("role") != "assistant":
            continue
        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            tool_type = part.get("type")
            output = part.get("output")
            if (
                part.get("state") != "output-available"
                or not isinstance(tool_type, str)
                or not isinstance(output, dict)
                or output.get("success") is not True
            ):
                continue
            if tool_type == "tool-inspect_notebook":
                part["output"] = {
                    "success": True,
                    "output": (
                        "Earlier notebook inspection compacted. Inspect the "
                        "live notebook again if current state is required."
                    ),
                    "stdout": [],
                    "stderr": [],
                    "errors": [],
                    "error": None,
                }
            elif tool_type == "tool-apply_notebook_patch":
                part["input"] = _compact_patch_input(part.get("input"))
    return compacted


def _compact_patch_input(value: object) -> object:
    if not isinstance(value, dict):
        return value

    def compact_cells(key: str) -> list[dict[str, object]] | None:
        cells = value.get(key)
        if not isinstance(cells, list):
            return None
        compacted_cells: list[dict[str, object]] = []
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            code = cell.get("code")
            code_chars = len(code) if isinstance(code, str) else 0
            compacted_cell = {
                field: cell.get(field)
                for field in ("cell_id", "after_cell_id")
                if field in cell
            }
            compacted_cell["code"] = (
                "# Earlier patch source compacted "
                f"({code_chars} characters). Inspect the live notebook for "
                "current source."
            )
            compacted_cells.append(compacted_cell)
        return compacted_cells

    compacted: dict[str, object] = {
        "delete_cell_ids": value.get("delete_cell_ids")
    }
    # Retain support for conversations created before the patch schema split.
    if (legacy_cells := compact_cells("cells")) is not None:
        compacted["cells"] = legacy_cells
    if (replacements := compact_cells("replacements")) is not None:
        compacted["replacements"] = replacements
    if (insertions := compact_cells("insertions")) is not None:
        compacted["insertions"] = insertions
    return compacted


def build_execute_code_toolset(
    session: Session,
    request: Request,
) -> FunctionToolset:
    """Build a `FunctionToolset` exposing one tool: `execute_code`.

    The tool is bound to the caller's *session* and *request*; the model
    never sees or passes a session id. Screenshot credentials are derived
    per tool call from the request so `ctx.screenshot()` can call back
    into this server (see `marimo/_code_mode/_context.py`).
    """

    from pydantic_ai import FunctionToolset

    toolset: FunctionToolset = FunctionToolset()

    async def execute_code(code: str) -> CodeExecutionResult:
        """Run Python inside the running notebook's kernel scratchpad.

        Use this for all notebook mutations via `marimo._code_mode`.
        """
        server_url, auth_token = get_code_mode_credentials(
            AppState(request), request
        )
        return await run_scratchpad_code(
            session,
            request,
            code=code,
            server_url=server_url,
            auth_token=auth_token,
        )

    toolset.add_function(
        execute_code,
        name="execute_code",
        description=execute_code.__doc__,
    )
    return toolset


def build_hybrid_code_mode_toolset(
    session: Session,
    request: Request,
) -> FunctionToolset:
    """Build typed notebook tools plus scratch Python for exploration.

    The mutation tools deliberately compile to the existing `_code_mode`
    transaction API. This keeps validation, staleness handling, execution, and
    persistence in one place while giving the model a smaller typed surface.
    """
    from pydantic_ai import FunctionToolset

    toolset: FunctionToolset = FunctionToolset()

    async def run(code: str) -> CodeExecutionResult:
        server_url, auth_token = get_code_mode_credentials(
            AppState(request), request
        )
        return await run_scratchpad_code(
            session,
            request,
            code=code,
            server_url=server_url,
            auth_token=auth_token,
        )

    async def execute_code(code: str) -> CodeExecutionResult:
        """Run exploratory Python in the live kernel without changing cells.

        Use the typed notebook tools for every persistent notebook mutation.
        Notebook-private names beginning with `_` are cell-scoped and cannot
        be read here; verify public outputs or recompute the intermediate.
        """
        if _imports_code_mode(code):
            return CodeExecutionResult(
                success=False,
                errors=[
                    (
                        "execute_code is exploration-only in hybrid mode; "
                        "use the typed notebook mutation tools instead"
                    )
                ],
            )
        return await run(code)

    async def inspect_notebook(
        scope: Literal["all", "outline", "errors", "history"],
    ) -> CodeExecutionResult:
        """Inspect notebook structure, source, failures, or prior revisions.

        Use `all` when source is required for an edit, `outline` for compact
        structure and dependency metadata, or `errors` for non-idle cells and
        their source. Every scope includes stable IDs, status, and errors. If
        an unsaved live edit differs from the document, inspection reports
        `source_diverged`; source-bearing scopes also include `runtime_code`.
        Use `history` only to restore source replaced or deleted by an earlier
        agent mutation. It returns a bounded, chronological revision list and
        reports whether older revisions were truncated.
        """
        if scope == "history":
            return await run(
                "import json as _json\n"
                "import marimo._code_mode as _cm\n"
                "async with _cm.get_context() as _ctx:\n"
                "    _revisions = [\n"
                "        {\n"
                "            'sequence': _revision.sequence,\n"
                "            'cell_id': str(_cell_id),\n"
                "            'name': _revision.name,\n"
                "            'code': _revision.code,\n"
                "        }\n"
                "        for _cell_id, _cell_revisions in "
                "_ctx._kernel.agent.revisions.all().items()\n"
                "        for _revision in _cell_revisions\n"
                "    ]\n"
                "    _history_truncated = "
                "_ctx._kernel.agent.revisions.truncated\n"
                "_revisions.sort(key=lambda _revision: "
                "_revision['sequence'])\n"
                "print(_json.dumps({\n"
                "    'revisions': _revisions,\n"
                "    'truncated': _history_truncated,\n"
                "}))"
            )
        return await run(
            "import json as _json\n"
            "import marimo._code_mode as _cm\n"
            "from marimo._ast.compiler import compile_cell as _compile_cell\n"
            f"_scope = {_python_literal(scope)}\n"
            "async with _cm.get_context() as _ctx:\n"
            "    _raw_cells = []\n"
            "    for _cell in _ctx.cells:\n"
            "        _impl = _ctx.graph.cells.get(_cell.id)\n"
            "        _compile_error = None\n"
            "        try:\n"
            "            if _impl is None:\n"
            "                _impl = _compile_cell(\n"
            "                    _cell.code, cell_id=_cell.id\n"
            "                )\n"
            "        except Exception as _exception:\n"
            "            _compile_error = str(_exception)\n"
            "        _raw_cells.append((_cell, _impl, _compile_error))\n"
            "    _owners = {\n"
            "        _name: str(_cell.id)\n"
            "        for _cell, _impl, _ in _raw_cells if _impl is not None\n"
            "        for _name in _impl.defs\n"
            "    }\n"
            "    _parents = {str(_cell.id): sorted({\n"
            "        _owners[_ref] for _ref in (_impl.refs if _impl else set())\n"
            "        if _ref in _owners\n"
            "    }) for _cell, _impl, _ in _raw_cells}\n"
            "    _children = {\n"
            "        str(_cell.id): [] for _cell, _, _ in _raw_cells\n"
            "    }\n"
            "    for _child_id, _parent_ids in _parents.items():\n"
            "        for _parent_id in _parent_ids:\n"
            "            _children[_parent_id].append(_child_id)\n"
            "    _cells = [{\n"
            "            'id': str(_cell.id),\n"
            "            'name': _cell.name,\n"
            "            'status': _cell.status,\n"
            "            'errors': [\n"
            "                *[str(_error) for _error in _cell.errors],\n"
            "                *([_compile_error] if _compile_error else []),\n"
            "            ],\n"
            "            'defines': sorted(_impl.defs) if _impl else [],\n"
            "            'references': sorted(_impl.refs) if _impl else [],\n"
            "            'parents': _parents[str(_cell.id)],\n"
            "            'children': sorted(_children[str(_cell.id)]),\n"
            "            'code_chars': len(_cell.code),\n"
            "            **({'code': _cell.code} if _scope != 'outline' "
            "else {}),\n"
            "            **({\n"
            "                'source_diverged': True,\n"
            "                'runtime_code_chars': len(_impl.code),\n"
            "                **(\n"
            "                    {'runtime_code': _impl.code}\n"
            "                    if _scope != 'outline' else {}\n"
            "                ),\n"
            "            } if (\n"
            "                _impl is not None and _cell.code != _impl.code\n"
            "            ) else {}),\n"
            "        } for _cell, _impl, _compile_error in _raw_cells]\n"
            "    if _scope == 'errors':\n"
            "        _cells = [\n"
            "            _cell for _cell in _cells\n"
            "            if _cell['errors'] or _cell['status'] not in "
            "('idle', 'disabled')\n"
            "        ]\n"
            "print(_json.dumps({'cells': _cells}, default=str))"
        )

    async def apply_notebook_patch(
        replacements: list[NotebookCellReplacement] | None = None,
        insertions: list[NotebookCellInsertion] | None = None,
        delete_cell_ids: list[str] | None = None,
    ) -> CodeExecutionResult:
        """Atomically apply cell edits, inserts, and deletes, then execute once.

        Put edits to existing stable IDs in `replacements`. Put new cells in
        `insertions`; new cells never accept a caller-supplied ID and may be
        placed after an existing `after_cell_id`. Batch every coherent edit
        and insertion in this one call rather than patching one cell at a time.
        Public top-level names must be unique across cells; prefix cell-local
        variables, including loop targets, with `_`. All structural changes
        validate as one transaction. Stale existing cells and patched cells
        then execute together in dependency order. Returns server-created IDs.
        A clean patch stays compact; a warning appears only when an edited
        cell unexpectedly loses its visible output.
        """
        replacement_cells = replacements or []
        inserted_cells = insertions or []
        delete_ids = delete_cell_ids or []
        edited_ids = [cell.cell_id for cell in replacement_cells]
        duplicate_edits = {
            cell_id for cell_id in edited_ids if edited_ids.count(cell_id) > 1
        }
        conflicts = duplicate_edits | (set(edited_ids) & set(delete_ids))
        if conflicts:
            names = ", ".join(sorted(conflicts))
            return CodeExecutionResult(
                success=False,
                errors=[f"Patch has conflicting cell operations: {names}"],
            )
        if len(delete_ids) != len(set(delete_ids)):
            return CodeExecutionResult(
                success=False,
                errors=["Patch contains duplicate delete_cell_ids"],
            )

        replacement_values = [asdict(cell) for cell in replacement_cells]
        insertion_values = [asdict(cell) for cell in inserted_cells]
        return await run(
            "import ast as _ast\n"
            "import json as _json\n"
            "import marimo._code_mode as _cm\n"
            "def _has_display_expression(_code):\n"
            "    try:\n"
            "        _body = _ast.parse(_code).body\n"
            "    except SyntaxError:\n"
            "        return False\n"
            "    if not _body or not isinstance(_body[-1], _ast.Expr):\n"
            "        return False\n"
            "    _value = _body[-1].value\n"
            "    return not (\n"
            "        isinstance(_value, _ast.Constant)\n"
            "        and isinstance(_value.value, str)\n"
            "    )\n"
            f"_replacements = {_python_literal(replacement_values)}\n"
            f"_insertions = {_python_literal(insertion_values)}\n"
            f"_delete_ids = {_python_literal(delete_ids)}\n"
            "async with _cm.get_context() as _ctx:\n"
            "    _before = {str(_cell.id): {\n"
            "        'has_output': _cell.output is not None,\n"
            "        'has_display_expression': (\n"
            "            _has_display_expression(_cell.code)\n"
            "        ),\n"
            "    } for _cell in _ctx.cells}\n"
            "    _stale_ids = [\n"
            "        str(_cell.id) for _cell in _ctx.cells\n"
            "        if _cell.status == 'stale' and str(_cell.id) not in "
            "_delete_ids\n"
            "    ]\n"
            "    _created_ids = []\n"
            "    _edited_ids = []\n"
            "    for _replacement in _replacements:\n"
            "        _cell_id = _replacement['cell_id']\n"
            "        _ctx.cells[_cell_id].code\n"
            "        _ctx.edit_cell(\n"
            "            _cell_id, code=_replacement['code']\n"
            "        )\n"
            "        _edited_ids.append(_cell_id)\n"
            "    for _insertion in _insertions:\n"
            "        _cell_id = str(_ctx.create_cell(\n"
            "            _insertion['code'],\n"
            "            after=_insertion['after_cell_id'],\n"
            "            hide_code=False,\n"
            "        ))\n"
            "        _created_ids.append(_cell_id)\n"
            "    for _cell_id in _delete_ids:\n"
            "        _ctx.cells[_cell_id].code\n"
            "        _ctx.delete_cell(_cell_id)\n"
            "    for _cell_id in dict.fromkeys(\n"
            "        [*_stale_ids, *_edited_ids, *_created_ids]\n"
            "    ):\n"
            "        _ctx.run_cell(_cell_id)\n"
            "_warnings = []\n"
            "async with _cm.get_context() as _verify_ctx:\n"
            "    for _cell_id in _edited_ids:\n"
            "        _cell = _verify_ctx.cells[_cell_id]\n"
            "        _prior = _before.get(_cell_id)\n"
            "        if (\n"
            "            _prior is not None\n"
            "            and _cell.status == 'idle'\n"
            "            and _prior['has_output']\n"
            "            and _cell.output is None\n"
            "        ):\n"
            "            _warnings.append(\n"
            "                f'Cell {_cell_id!r} previously produced visible '\n"
            "                'output; it now produces none'\n"
            "            )\n"
            "        elif (\n"
            "            _prior is not None\n"
            "            and _cell.status == 'idle'\n"
            "            and _prior['has_display_expression']\n"
            "            and not _has_display_expression(_cell.code)\n"
            "        ):\n"
            "            _warnings.append(\n"
            "                f'Cell {_cell_id!r} previously ended in a '\n"
            "                'display expression; the replacement does not'\n"
            "            )\n"
            "_result = {\n"
            "    'operation': 'patch',\n"
            "    'created_cell_ids': _created_ids,\n"
            "    'edited_cell_ids': _edited_ids,\n"
            "    'deleted_cell_ids': _delete_ids,\n"
            "    'executed_stale_cell_ids': _stale_ids,\n"
            "}\n"
            "if _warnings:\n"
            "    _result['warnings'] = _warnings\n"
            "print(_json.dumps(_result))"
        )

    async def run_cells(cell_ids: list[str]) -> CodeExecutionResult:
        """Run existing cells by stable ID as one reactive batch."""
        return await run(
            "import json as _json\n"
            "import marimo._code_mode as _cm\n"
            f"_cell_ids = {_python_literal(cell_ids)}\n"
            "async with _cm.get_context() as _ctx:\n"
            "    for _cell_id in _cell_ids:\n"
            "        _ctx.run_cell(_cell_id)\n"
            "print(_json.dumps({'operation': 'run', "
            "'cell_ids': _cell_ids}))"
        )

    async def manage_packages(
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> CodeExecutionResult:
        """Install or remove notebook packages as one environment operation.

        Package strings may include version constraints or local paths.
        Environment changes happen before later notebook patches and may
        report that a kernel restart is required.
        """
        packages_to_add = add or []
        packages_to_remove = remove or []
        if not packages_to_add and not packages_to_remove:
            return CodeExecutionResult(
                success=False,
                errors=["Specify at least one package to add or remove"],
            )
        return await run(
            "import json as _json\n"
            "import marimo._code_mode as _cm\n"
            f"_packages_to_add = {_python_literal(packages_to_add)}\n"
            f"_packages_to_remove = {_python_literal(packages_to_remove)}\n"
            "async with _cm.get_context() as _ctx:\n"
            "    if _packages_to_add:\n"
            "        _ctx.packages.add(_packages_to_add)\n"
            "    if _packages_to_remove:\n"
            "        _ctx.packages.remove(_packages_to_remove)\n"
            "print(_json.dumps({\n"
            "    'operation': 'packages',\n"
            "    'requested_additions': _packages_to_add,\n"
            "    'requested_removals': _packages_to_remove,\n"
            "}))"
        )

    async def set_ui_value(
        variable_name: str, value: object
    ) -> CodeExecutionResult:
        """Set one live `mo.ui` element by its notebook variable name."""
        return await run(
            "import json as _json\n"
            "import marimo._code_mode as _cm\n"
            f"_variable_name = {_python_literal(variable_name)}\n"
            f"_value = {_python_literal(value)}\n"
            "async with _cm.get_context() as _ctx:\n"
            "    if _variable_name not in _ctx.globals:\n"
            "        raise KeyError(\n"
            "            f'No live notebook variable {_variable_name!r}'\n"
            "        )\n"
            "    _ctx.set_ui_value(_ctx.globals[_variable_name], _value)\n"
            "print(_json.dumps({\n"
            "    'operation': 'set_ui_value',\n"
            "    'variable_name': _variable_name,\n"
            "    'value': _value,\n"
            "}, default=str))"
        )

    async def configure_notebook(
        cells: list[NotebookCellConfiguration],
    ) -> CodeExecutionResult:
        """Update existing cell presentation or visual ordering in one batch.

        Configuration fields left as `None` remain unchanged. A cell may move
        before or after another stable cell ID, but not both.
        """
        conflicting_moves = [
            cell.cell_id
            for cell in cells
            if cell.move_before_cell_id is not None
            and cell.move_after_cell_id is not None
        ]
        if conflicting_moves:
            names = ", ".join(sorted(conflicting_moves))
            return CodeExecutionResult(
                success=False,
                errors=[f"Cells cannot move both before and after: {names}"],
            )
        configuration_values = [asdict(cell) for cell in cells]
        return await run(
            "import json as _json\n"
            "import marimo._code_mode as _cm\n"
            f"_configurations = {_python_literal(configuration_values)}\n"
            "async with _cm.get_context() as _ctx:\n"
            "    for _configuration in _configurations:\n"
            "        _cell_id = _configuration['cell_id']\n"
            "        _overrides = {\n"
            "            _key: _configuration[_key]\n"
            "            for _key in (\n"
            "                'hide_code', 'disabled', 'expand_output', 'column'\n"
            "            )\n"
            "            if _configuration[_key] is not None\n"
            "        }\n"
            "        if _overrides:\n"
            "            _ctx.edit_cell(_cell_id, **_overrides)\n"
            "        if _configuration['move_before_cell_id'] is not None:\n"
            "            _ctx.move_cell(\n"
            "                _cell_id,\n"
            "                before=_configuration['move_before_cell_id'],\n"
            "            )\n"
            "        elif _configuration['move_after_cell_id'] is not None:\n"
            "            _ctx.move_cell(\n"
            "                _cell_id,\n"
            "                after=_configuration['move_after_cell_id'],\n"
            "            )\n"
            "print(_json.dumps({\n"
            "    'operation': 'configure_notebook',\n"
            "    'cell_ids': [\n"
            "        _configuration['cell_id']\n"
            "        for _configuration in _configurations\n"
            "    ],\n"
            "}))"
        )

    toolset.add_function(execute_code, description=execute_code.__doc__)
    toolset.add_function(
        inspect_notebook, description=inspect_notebook.__doc__
    )
    toolset.add_function(
        apply_notebook_patch, description=apply_notebook_patch.__doc__
    )
    toolset.add_function(run_cells, description=run_cells.__doc__)
    toolset.add_function(manage_packages, description=manage_packages.__doc__)
    toolset.add_function(set_ui_value, description=set_ui_value.__doc__)
    toolset.add_function(
        configure_notebook, description=configure_notebook.__doc__
    )

    return toolset


def references_capability() -> list[Capability]:
    from pydantic_ai.capabilities import Capability

    gotchas_capability: Capability = Capability(
        id="gotchas",
        description=(
            "Name redefinition, cached module proxies, and other notebook traps."
        ),
        instructions=load_reference("gotchas"),
        defer_loading=True,
    )

    notebook_improvements_capability: Capability = Capability(
        id="notebook-improvements",
        description="Improving, optimizing, or cleaning up an existing notebook.",
        instructions=load_reference("notebook-improvements"),
        defer_loading=True,
    )

    rich_representations_capability: Capability = Capability(
        id="rich-representations",
        description="Custom widgets, visual encodings, and interactive output.",
        instructions=load_reference("rich-representations"),
        defer_loading=True,
    )

    return [
        gotchas_capability,
        notebook_improvements_capability,
        rich_representations_capability,
    ]
