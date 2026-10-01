# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import inspect
from collections.abc import Awaitable, Callable
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.requires("pydantic_ai")
def test_build_execute_code_toolset_exposes_single_execute_code_tool() -> None:
    from marimo._server.ai.tools.code_mode import build_execute_code_toolset

    toolset = build_execute_code_toolset(MagicMock(), MagicMock())

    assert list(toolset.tools.keys()) == ["execute_code"]
    tool = toolset.tools["execute_code"]
    # The model is told how to use the tool via its description.
    assert tool.description
    assert "scratchpad" in tool.description


@pytest.mark.requires("pydantic_ai")
def test_build_hybrid_toolset_exposes_editor_tools() -> None:
    from marimo._server.ai.tools.code_mode import (
        build_hybrid_code_mode_toolset,
    )

    toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())

    assert list(toolset.tools) == [
        "execute_code",
        "inspect_notebook",
        "apply_notebook_patch",
        "run_cells",
        "manage_packages",
        "set_ui_value",
        "configure_notebook",
    ]
    assert (
        "without changing cells" in toolset.tools["execute_code"].description
    )
    assert (
        "private names beginning with `_`"
        in toolset.tools["execute_code"].description
    )
    inspect_signature = inspect.signature(
        toolset.tools["inspect_notebook"].function
    )
    assert list(inspect_signature.parameters) == ["scope", "cell_id"]
    patch_signature = inspect.signature(
        toolset.tools["apply_notebook_patch"].function
    )
    assert list(patch_signature.parameters) == [
        "replacements",
        "insertions",
        "delete_cell_ids",
    ]


@pytest.mark.requires("pydantic_ai")
async def test_inspect_notebook_compiles_requested_scope() -> None:
    from marimo._server.ai.tools.code_mode import (
        build_hybrid_code_mode_toolset,
    )

    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost:2718", "secret-token"),
        ),
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())
        inspect_notebook = cast(
            Callable[..., Awaitable[object]],
            toolset.tools["inspect_notebook"].function,
        )

        await inspect_notebook(scope="outline")

    source = mock_run.await_args.kwargs["code"]
    assert "_scope = 'outline'" in source
    assert "'code_chars': len(_cell.code)" in source
    assert "'source_diverged': True" in source
    assert "'runtime_code': _impl.code" in source
    assert "_cell.code != _impl.code" in source
    assert "if _scope == 'errors'" in source


@pytest.mark.requires("pydantic_ai")
async def test_inspect_notebook_compiles_revision_history() -> None:
    from marimo._server.ai.tools.code_mode import (
        build_hybrid_code_mode_toolset,
    )

    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost:2718", "secret-token"),
        ),
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())
        inspect_notebook = cast(
            Callable[..., Awaitable[object]],
            toolset.tools["inspect_notebook"].function,
        )

        await inspect_notebook(scope="history")

    source = mock_run.await_args.kwargs["code"]
    assert "_ctx._kernel.agent.revisions.all()" in source
    assert "'sequence': _revision.sequence" in source
    assert "'code': _revision.code" in source
    assert (
        "_history_truncated = _ctx._kernel.agent.revisions.truncated" in source
    )
    assert "'truncated': _history_truncated" in source


@pytest.mark.requires("pydantic_ai")
async def test_inspect_notebook_returns_rendered_output_as_image() -> None:
    from pydantic_ai import BinaryImage, ToolReturn, ToolReturnPart

    from marimo._ai._tools.types import CodeExecutionResult
    from marimo._server.ai.tools.code_mode import (
        build_hybrid_code_mode_toolset,
    )

    png = b"\x89PNG\r\n\x1a\n"
    data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    result = CodeExecutionResult(
        success=True,
        output=data_url,
    )
    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost:2718", "secret-token"),
        ),
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new_callable=AsyncMock,
            return_value=result,
        ) as mock_run,
    ):
        toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())
        inspect_notebook = cast(
            Callable[..., Awaitable[object]],
            toolset.tools["inspect_notebook"].function,
        )

        returned = await inspect_notebook(
            scope="rendered_output", cell_id="chart"
        )

    assert isinstance(returned, ToolReturn)
    structured_result, image = returned.return_value
    assert structured_result["success"] is True
    assert structured_result["output"] == ("Captured 8 PNG bytes from 'chart'")
    assert isinstance(image, BinaryImage)
    assert image.data == png
    tool_part = ToolReturnPart(
        tool_name="inspect_notebook",
        tool_call_id="call-1",
        content=returned.return_value,
    )
    _, model_content = tool_part.model_response_str_and_user_content()
    assert image in model_content
    source = mock_run.await_args.kwargs["code"]
    assert "_ScreenshotOutput(_image)" in source
    assert "await _ctx.screenshot(" in source
    assert "_target_cell_id = 'chart'" in source
    assert mock_run.await_args.kwargs["timeout"] == 300.0
    compile(
        source,
        "<inspect_notebook rendered_output>",
        "exec",
        ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
    )


@pytest.mark.requires("pydantic_ai")
async def test_inspect_notebook_cell_id_selects_rendered_output() -> None:
    from marimo._ai._tools.types import CodeExecutionResult
    from marimo._server.ai.tools.code_mode import (
        build_hybrid_code_mode_toolset,
    )

    png = b"\x89PNG\r\n\x1a\n"
    data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())
    inspect_notebook = cast(
        Callable[..., Awaitable[object]],
        toolset.tools["inspect_notebook"].function,
    )

    with patch(
        "marimo._server.ai.tools.code_mode.run_scratchpad_code",
        new_callable=AsyncMock,
        return_value=CodeExecutionResult(success=True, output=data_url),
    ) as mock_run:
        await inspect_notebook(scope="all", cell_id="chart")

    source = mock_run.await_args.kwargs["code"]
    assert "_ScreenshotOutput(_image)" in source
    assert "_target_cell_id = 'chart'" in source


def test_get_tool_strategy_defaults_to_balanced_hybrid() -> None:
    from marimo._server.ai.tools.code_mode import get_tool_strategy

    request = MagicMock()
    request.headers = {}

    assert get_tool_strategy(request) == "hybrid_balanced"


def test_get_tool_strategy_accepts_explicit_code_mode_header() -> None:
    from marimo._server.ai.tools.code_mode import (
        TOOL_STRATEGY_HEADER,
        get_tool_strategy,
    )

    request = MagicMock()
    request.headers = {TOOL_STRATEGY_HEADER: "code_mode"}

    assert get_tool_strategy(request) == "code_mode"


def test_get_tool_strategy_rejects_legacy_hybrid_header() -> None:
    from marimo._server.ai.tools.code_mode import (
        TOOL_STRATEGY_HEADER,
        get_tool_strategy,
    )

    request = MagicMock()
    request.headers = {TOOL_STRATEGY_HEADER: "hybrid"}

    assert get_tool_strategy(request) == "code_mode"


def test_get_tool_strategy_accepts_balanced_hybrid_header() -> None:
    from marimo._server.ai.tools.code_mode import (
        TOOL_STRATEGY_HEADER,
        get_tool_strategy,
    )

    request = MagicMock()
    request.headers = {TOOL_STRATEGY_HEADER: "hybrid_balanced"}

    assert get_tool_strategy(request) == "hybrid_balanced"


def test_get_tool_strategy_rejects_unknown_header() -> None:
    from marimo._server.ai.tools.code_mode import (
        TOOL_STRATEGY_HEADER,
        get_tool_strategy,
    )

    request = MagicMock()
    request.headers = {TOOL_STRATEGY_HEADER: "unknown"}

    assert get_tool_strategy(request) == "code_mode"


def test_get_history_strategy_defaults_to_semantic() -> None:
    from marimo._server.ai.tools.code_mode import get_history_strategy

    request = MagicMock()
    request.headers = {}

    assert get_history_strategy(request) == "semantic"


def test_get_history_strategy_accepts_uncompacted_control() -> None:
    from marimo._server.ai.tools.code_mode import (
        HISTORY_STRATEGY_HEADER,
        get_history_strategy,
    )

    request = MagicMock()
    request.headers = {HISTORY_STRATEGY_HEADER: "none"}

    assert get_history_strategy(request) == "none"


def test_hybrid_execute_code_rejects_code_mode_import() -> None:
    from marimo._server.ai.tools.code_mode import _imports_code_mode

    assert _imports_code_mode("import marimo._code_mode as cm")
    assert _imports_code_mode("from marimo import _code_mode")
    assert _imports_code_mode("from marimo._code_mode import get_context")
    assert not _imports_code_mode("import marimo as mo")


def test_compact_hybrid_history_preserves_latest_turn_and_errors() -> None:
    from marimo._server.ai.tools.code_mode import compact_hybrid_history

    messages = [
        {"role": "user", "parts": [{"type": "text", "text": "first"}]},
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool-inspect_notebook",
                    "state": "output-available",
                    "input": {"scope": "all"},
                    "output": {"success": True, "stdout": ["large source"]},
                },
                {
                    "type": "tool-apply_notebook_patch",
                    "state": "output-available",
                    "input": {
                        "cells": [
                            {
                                "cell_id": "cell-1",
                                "after_cell_id": None,
                                "code": "answer = 42",
                            }
                        ],
                        "delete_cell_ids": [],
                    },
                    "output": {"success": True},
                },
                {
                    "type": "tool-execute_code",
                    "state": "output-error",
                    "input": {"code": "missing"},
                    "errorText": "NameError",
                },
            ],
        },
        {"role": "user", "parts": [{"type": "text", "text": "second"}]},
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool-inspect_notebook",
                    "state": "output-available",
                    "input": {"scope": "all"},
                    "output": {"success": True, "stdout": ["latest"]},
                }
            ],
        },
        {"role": "user", "parts": [{"type": "text", "text": "third"}]},
    ]

    compacted = compact_hybrid_history(messages)

    old_parts = compacted[1]["parts"]
    assert old_parts[0]["output"]["output"].startswith("Earlier notebook")
    assert old_parts[1]["input"] == messages[1]["parts"][1]["input"]
    assert old_parts[2]["errorText"] == "NameError"
    assert compacted[3] == messages[3]
    assert messages[1]["parts"][0]["output"]["stdout"] == ["large source"]


def test_compact_hybrid_history_leaves_one_turn_unchanged() -> None:
    from marimo._server.ai.tools.code_mode import compact_hybrid_history

    messages = [
        {"role": "user", "parts": []},
        {"role": "assistant", "parts": []},
        {"role": "user", "parts": []},
    ]

    assert compact_hybrid_history(messages) is messages


def test_compact_hybrid_history_removes_old_rendered_images() -> None:
    from marimo._server.ai.tools.code_mode import compact_hybrid_history

    messages = [
        {"role": "user", "parts": []},
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool-inspect_notebook",
                    "state": "output-available",
                    "input": {
                        "scope": "rendered_output",
                        "cell_id": "chart",
                    },
                    "output": [
                        {"success": True, "output": "Captured PNG"},
                        {"kind": "binary", "data": "large-base64-image"},
                    ],
                }
            ],
        },
        {"role": "user", "parts": []},
        {"role": "assistant", "parts": []},
        {"role": "user", "parts": []},
    ]

    compacted = compact_hybrid_history(messages)

    assert compacted[1]["parts"][0]["output"] == {
        "success": True,
        "output": (
            "Earlier notebook inspection compacted. Inspect the live "
            "notebook again if current state is required."
        ),
        "stdout": [],
        "stderr": [],
        "errors": [],
        "error": None,
    }


@pytest.mark.requires("pydantic_ai")
def test_compact_consumed_screenshot_images_only_after_response() -> None:
    from pydantic_ai import BinaryImage
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolReturnPart,
    )

    from marimo._server.ai.tools.code_mode import (
        compact_consumed_screenshot_images,
    )

    screenshot = ToolReturnPart(
        tool_name="inspect_notebook",
        tool_call_id="screenshot-1",
        content=[
            {"success": True, "output": "Captured PNG"},
            BinaryImage(data=b"png-bytes", media_type="image/png"),
        ],
    )
    request = ModelRequest(parts=[screenshot])

    assert compact_consumed_screenshot_images([request]) == [request]

    response = ModelResponse(parts=[TextPart(content="I inspected it")])
    compacted = compact_consumed_screenshot_images([request, response])

    compacted_request = compacted[0]
    assert isinstance(compacted_request, ModelRequest)
    compacted_part = compacted_request.parts[0]
    assert isinstance(compacted_part, ToolReturnPart)
    assert compacted_part.content == [
        {"success": True, "output": "Captured PNG"}
    ]
    assert screenshot.files
    assert not compacted_part.files


@pytest.mark.requires("pydantic_ai")
def test_compact_consumed_screenshot_images_preserves_other_images() -> None:
    from pydantic_ai import BinaryImage
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolReturnPart,
    )

    from marimo._server.ai.tools.code_mode import (
        compact_consumed_screenshot_images,
    )

    image = BinaryImage(data=b"image", media_type="image/png")
    request = ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name="some_other_tool",
                tool_call_id="other-1",
                content=[image],
            )
        ]
    )
    response = ModelResponse(parts=[TextPart(content="done")])

    assert compact_consumed_screenshot_images([request, response]) == [
        request,
        response,
    ]


@pytest.mark.requires("pydantic_ai")
async def test_execute_code_tool_routes_to_scratchpad_with_credentials() -> (
    None
):
    from marimo._server.ai.tools.code_mode import build_execute_code_toolset

    session = MagicMock()
    request = MagicMock()
    sentinel_result = MagicMock(name="CodeExecutionResult")

    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost:2718", "secret-token"),
        ) as mock_creds,
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new_callable=AsyncMock,
            return_value=sentinel_result,
        ) as mock_run,
        patch("marimo._server.ai.tools.code_mode.AppState") as mock_app_state,
    ):
        app_state_instance = cast(MagicMock, mock_app_state.return_value)
        toolset = build_execute_code_toolset(session, request)
        execute_code = cast(
            Callable[[str], Awaitable[object]],
            toolset.tools["execute_code"].function,
        )

        result = await execute_code("print('hi')")

    assert result is sentinel_result
    # Credentials are derived from the bound request, not model input.
    mock_creds.assert_called_once_with(app_state_instance, request)
    mock_run.assert_awaited_once_with(
        session,
        request,
        code="print('hi')",
        server_url="http://localhost:2718",
        auth_token="secret-token",
        timeout=60.0,
    )


@pytest.mark.requires("pydantic_ai")
async def test_hybrid_patch_compiles_to_one_code_mode_transaction() -> None:
    from marimo._server.ai.tools.code_mode import (
        NotebookCellInsertion,
        NotebookCellReplacement,
        build_hybrid_code_mode_toolset,
    )

    session = MagicMock()
    request = MagicMock()
    sentinel_result = MagicMock(name="CodeExecutionResult")

    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost:2718", "secret-token"),
        ),
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new_callable=AsyncMock,
            return_value=sentinel_result,
        ) as mock_run,
    ):
        toolset = build_hybrid_code_mode_toolset(session, request)
        apply_notebook_patch = cast(
            Callable[..., Awaitable[object]],
            toolset.tools["apply_notebook_patch"].function,
        )
        result = await apply_notebook_patch(
            replacements=[
                NotebookCellReplacement(code="answer = 42", cell_id="cell-1"),
            ],
            insertions=[
                NotebookCellInsertion(
                    code="double = answer * 2",
                    after_cell_id="cell-1",
                ),
            ],
            delete_cell_ids=["cell-old"],
        )

    assert result is sentinel_result
    source = mock_run.await_args.kwargs["code"]
    assert "'cell_id': 'cell-1'" in source
    assert "'code': 'answer = 42'" in source
    assert "'code': 'double = answer * 2'" in source
    assert "_ctx.edit_cell(" in source
    assert "_ctx.create_cell(" in source
    assert "_ctx.delete_cell(_cell_id)" in source
    assert "[*_stale_ids, *_edited_ids, *_created_ids]" in source
    assert "_cell.has_output" in source
    assert "_has_display_expression(_cell.code)" in source
    assert "previously produced visible" in source
    assert "previously ended in a" in source
    assert "if _warnings:" in source
    assert "'cells': _cell_results" in source
    assert mock_run.await_args.kwargs["timeout"] == 300.0
    compile(
        source,
        "<apply_notebook_patch>",
        "exec",
        ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
    )


@pytest.mark.requires("pydantic_ai")
async def test_hybrid_patch_rejects_conflicting_operations() -> None:
    from marimo._server.ai.tools.code_mode import (
        NotebookCellReplacement,
        build_hybrid_code_mode_toolset,
    )

    toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())
    apply_notebook_patch = cast(
        Callable[..., Awaitable[object]],
        toolset.tools["apply_notebook_patch"].function,
    )

    result = await apply_notebook_patch(
        replacements=[
            NotebookCellReplacement(code="answer = 42", cell_id="cell-1")
        ],
        delete_cell_ids=["cell-1"],
    )

    assert result.success is False
    assert result.errors == ["Patch has conflicting cell operations: cell-1"]


@pytest.mark.requires("pydantic_ai")
async def test_balanced_tools_compile_to_code_mode_operations() -> None:
    from marimo._server.ai.tools.code_mode import (
        NotebookCellConfiguration,
        build_hybrid_code_mode_toolset,
    )

    with (
        patch(
            "marimo._server.ai.tools.code_mode.get_code_mode_credentials",
            return_value=("http://localhost:2718", "secret-token"),
        ),
        patch(
            "marimo._server.ai.tools.code_mode.run_scratchpad_code",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())
        manage_packages = cast(
            Callable[..., Awaitable[object]],
            toolset.tools["manage_packages"].function,
        )
        set_ui_value = cast(
            Callable[..., Awaitable[object]],
            toolset.tools["set_ui_value"].function,
        )
        configure_notebook = cast(
            Callable[..., Awaitable[object]],
            toolset.tools["configure_notebook"].function,
        )

        await manage_packages(
            add=["local.whl"],
            remove=["old-package"],
            verify_imports=["local_package"],
        )
        package_source = mock_run.await_args.kwargs["code"]
        package_timeout = mock_run.await_args.kwargs["timeout"]
        await set_ui_value("multiplier", 4)
        ui_source = mock_run.await_args.kwargs["code"]
        await configure_notebook(
            [
                NotebookCellConfiguration(
                    cell_id="chart",
                    expand_output=True,
                    move_after_cell_id="summary",
                )
            ]
        )
        configuration_source = mock_run.await_args.kwargs["code"]

    assert "_ctx.packages.add(_packages_to_add)" in package_source
    assert "_ctx.packages.remove(_packages_to_remove)" in package_source
    assert "_ctx.packages.results" in package_source
    assert "'changed_packages': _changed_packages" in package_source
    assert (
        "'kernel_restart_required': _kernel_restart_required" in package_source
    )
    assert "_verify_ctx.packages.verify_imports(" in package_source
    assert package_timeout == 600.0
    compile(
        package_source,
        "<manage_packages>",
        "exec",
        ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
    )
    assert (
        "_ctx.set_ui_value(_ctx.globals[_variable_name], _value)" in ui_source
    )
    assert "_ctx.edit_cell(_cell_id, **_overrides)" in configuration_source
    assert "after=_configuration['move_after_cell_id']" in configuration_source


@pytest.mark.requires("pydantic_ai")
async def test_configure_notebook_rejects_ambiguous_move() -> None:
    from marimo._server.ai.tools.code_mode import (
        NotebookCellConfiguration,
        build_hybrid_code_mode_toolset,
    )

    toolset = build_hybrid_code_mode_toolset(MagicMock(), MagicMock())
    configure_notebook = cast(
        Callable[..., Awaitable[object]],
        toolset.tools["configure_notebook"].function,
    )

    result = await configure_notebook(
        [
            NotebookCellConfiguration(
                cell_id="chart",
                move_before_cell_id="summary",
                move_after_cell_id="summary",
            )
        ]
    )

    assert result.success is False
    assert result.errors == ["Cells cannot move both before and after: chart"]


@pytest.mark.requires("pydantic_ai")
def test_references_capability_exposes_deferred_reference_bundles() -> None:
    from marimo._server.ai.skills.utils import load_reference
    from marimo._server.ai.tools.code_mode import references_capability

    capabilities = references_capability()
    by_id = {capability.id: capability for capability in capabilities}

    assert set(by_id) == {
        "gotchas",
        "notebook-improvements",
        "rich-representations",
    }
    for capability in capabilities:
        assert capability.defer_loading is True
        assert capability.get_instructions() == [load_reference(capability.id)]

    assert "Name redefinition" in by_id["gotchas"].description
    assert (
        "Improving, optimizing" in by_id["notebook-improvements"].description
    )
    assert "Custom widgets" in by_id["rich-representations"].description
