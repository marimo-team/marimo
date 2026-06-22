# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import cast

import pytest

from marimo._ast.visitor import Language
from marimo._config.config import CopilotMode
from marimo._server.ai.prompts import (
    FIM_SUFFIX_TAG,
    _common_chat_sections,
    _format_plain_text,
    _format_schema_info,
    _format_variables,
    _get_mode_intro_message,
    get_chat_system_prompt,
    get_inline_system_prompt,
    get_refactor_or_insert_notebook_cell_system_prompt,
)
from marimo._server.ai.skills.utils import load_skill
from marimo._server.models.completion import (
    AiCompletionContext,
    SchemaColumn,
    SchemaTable,
    VariableContext,
)
from marimo._types.ids import SessionId
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def _header(title: str) -> str:
    return f"\n\n==================== {title} ====================\n\n"


def test_system_prompts():
    result = ""
    for language in ("python", "markdown", "sql", "idk"):
        result += _header(language)
        result += get_refactor_or_insert_notebook_cell_system_prompt(
            language=cast(Language, language),
            is_insert=False,
            support_multiple_cells=False,
            custom_rules=None,
            cell_code=None,
            selected_text=None,
            other_cell_codes=None,
            context=None,
        )

    result += _header("with custom rules")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules="Always use type hints.",
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=None,
    )

    result += _header("with context")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        support_multiple_cells=False,
        context=AiCompletionContext(
            schema=[
                SchemaTable(
                    name="df_1",
                    columns=[
                        SchemaColumn(
                            "age", "int", sample_values=["1", "2", "3"]
                        ),
                        SchemaColumn(
                            "name",
                            "str",
                            sample_values=["Alice", "Bob", "Charlie"],
                        ),
                    ],
                )
            ]
        ),
        is_insert=False,
        custom_rules=None,
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
    )

    # New test cases for get_refactor_or_insert_notebook_cell_system_prompt
    result += _header("with is_insert=True")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=True,
        support_multiple_cells=False,
        custom_rules=None,
        cell_code="def fib(n):\n    <insert_here></insert_here>",
        selected_text=None,
        other_cell_codes=None,
        context=None,
    )

    result += _header("with cell_code")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules=None,
        cell_code="def hello():\n    <rewrite_this>print('Hello, world!')</rewrite_this>",
        selected_text="print('Hello, world!')",
        other_cell_codes=None,
        context=None,
    )

    result += _header("with selected_text")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules=None,
        cell_code="def hello():\n    <rewrite_this>print('Hello, world!')</rewrite_this>",
        selected_text="print('Hello, world!')",
        other_cell_codes=None,
        context=None,
    )

    result += _header("with other_cell_codes")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules=None,
        cell_code="<rewrite_this>pl.DataFrame()</rewrite_this>",
        selected_text="pl.DataFrame()",
        other_cell_codes="import pandas as pd\nimport numpy as np",
        context=None,
    )

    result += _header("with VariableContext objects")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules=None,
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=AiCompletionContext(
            variables=[
                VariableContext(
                    name="df",
                    value_type="DataFrame",
                    preview_value="<DataFrame with 100 rows and 5 columns>",
                ),
                VariableContext(
                    name="model",
                    value_type="Model",
                    preview_value="<Model object>",
                ),
            ]
        ),
    )

    result += _header("with support_multiple_cells=True")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=True,
        custom_rules=None,
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=AiCompletionContext(
            variables=[
                VariableContext(
                    name="df",
                    value_type="DataFrame",
                    preview_value="<DataFrame with 100 rows and 5 columns>",
                ),
                VariableContext(
                    name="model",
                    value_type="Model",
                    preview_value="<Model object>",
                ),
            ]
        ),
    )

    snapshot("system_prompts.txt", result)


def test_empty_rules():
    assert get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules=None,
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=None,
    ) == get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules="  ",
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=None,
    )


def test_edit_inline_prompts():
    result = get_inline_system_prompt(language="python")
    snapshot("edit_inline_prompts.txt", result)
    assert FIM_SUFFIX_TAG in result


def test_chat_system_prompts():
    result: str = ""
    result += _header("no custom rules")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=None,
        mode="manual",
        session_id=SessionId("s_test"),  # stable fake session id for snapshot
    )

    result += _header("with custom rules")
    result += get_chat_system_prompt(
        custom_rules="Always be polite.",
        include_other_code="",
        context=None,
        mode="manual",
        session_id=SessionId("s_test"),
    )

    result += _header("with variables")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=AiCompletionContext(
            variables=["var1", "var2"],
        ),
        mode="manual",
        session_id=SessionId("s_test"),
    )

    result += _header("with VariableContext objects")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=AiCompletionContext(
            variables=[
                VariableContext(
                    name="df",
                    value_type="DataFrame",
                    preview_value="<DataFrame with 100 rows and 5 columns>",
                ),
                VariableContext(
                    name="model",
                    value_type="Model",
                    preview_value="<Model object>",
                ),
            ]
        ),
        mode="manual",
        session_id=SessionId("s_test"),
    )

    result += _header("with context")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=AiCompletionContext(
            schema=[
                SchemaTable(
                    name="df_1",
                    columns=[
                        SchemaColumn(
                            "age", "int", sample_values=["1", "2", "3"]
                        ),
                        SchemaColumn(
                            "name",
                            "str",
                            sample_values=["Alice", "Bob", "Charlie"],
                        ),
                    ],
                ),
                SchemaTable(
                    name="d2_2",
                    columns=[
                        SchemaColumn(
                            "a", "int", sample_values=["1", "2", "3"]
                        ),
                        SchemaColumn(
                            "b", "int", sample_values=["4", "5", "6"]
                        ),
                    ],
                ),
            ],
        ),
        mode="manual",
        session_id=SessionId("s_test"),
    )

    result += _header("with other code")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="import pandas as pd\nimport numpy as np\n",
        context=None,
        mode="manual",
        session_id=SessionId("s_test"),
    )

    result += _header("with agent mode")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=None,
        mode="agent",
        session_id=SessionId("s_test"),
    )

    result += _header("kitchen sink")
    result += get_chat_system_prompt(
        custom_rules="Always be polite.",
        include_other_code="import pandas as pd\nimport numpy as np\n",
        context=AiCompletionContext(
            variables=["var1", "var2"],
            schema=[
                SchemaTable(
                    name="df_1",
                    columns=[
                        SchemaColumn(
                            "age", "int", sample_values=["1", "2", "3"]
                        ),
                        SchemaColumn(
                            "name",
                            "str",
                            sample_values=["Alice", "Bob", "Charlie"],
                        ),
                    ],
                ),
            ],
        ),
        mode="manual",
        session_id=SessionId("s_test"),
    )

    snapshot("chat_system_prompts.txt", result)


def test_markdown_rules_include_latex():
    from marimo._server.ai.prompts import (
        get_chat_system_prompt,
        get_refactor_or_insert_notebook_cell_system_prompt,
    )

    # Test refactor prompt
    refactor_prompt = get_refactor_or_insert_notebook_cell_system_prompt(
        language="markdown",
        is_insert=False,
        support_multiple_cells=False,
        custom_rules=None,
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=None,
    )
    assert "double dollar signs ($$)" in refactor_prompt
    assert "$$E=mc^2$$" in refactor_prompt
    assert "Do NOT use single dollar signs" in refactor_prompt

    # Test chat prompt
    chat_prompt = get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=None,
        mode="manual",
        session_id=SessionId("test"),
    )
    assert "double dollar signs ($$)" in chat_prompt
    assert "$$E=mc^2$$" in chat_prompt
    assert "Do NOT use single dollar signs" in chat_prompt


def test_format_variables():
    """Test the _format_variables function."""
    # Test empty variables
    assert _format_variables(None) == ""
    assert _format_variables([]) == ""

    variables = [
        "var1",
        VariableContext(
            name="df",
            value_type="DataFrame",
            preview_value="<DataFrame with 100 rows and 5 columns>",
        ),
        "var2",
    ]
    expected = (
        "\n\n## Available variables from other cells:\n"
        "- variable: `var1`"
        "- variable: `df`\n"
        "  - value_type: DataFrame\n"
        "  - value_preview: <DataFrame with 100 rows and 5 columns>\n"
        "- variable: `var2`"
    )
    assert _format_variables(variables) == expected

    # Test private variables
    variables = [
        "var1",
        "_private_var",
        VariableContext(
            name="df",
            value_type="DataFrame",
            preview_value="<DataFrame with 100 rows and 5 columns>",
        ),
        VariableContext(
            name="_private_df",
            value_type="DataFrame",
            preview_value="<Private DataFrame>",
        ),
    ]
    expected = (
        "\n\n## Available variables from other cells:\n"
        "- variable: `var1`"
        "- variable: `df`\n"
        "  - value_type: DataFrame\n"
        "  - value_preview: <DataFrame with 100 rows and 5 columns>\n"
    )
    assert _format_variables(variables) == expected


def test_format_plain_text():
    assert _format_plain_text("") == ""
    assert _format_plain_text("  ") == ""
    assert (
        _format_plain_text("Hello, world!")
        == "If the prompt mentions @kind://name, use the following context to help you answer the question:\n\nHello, world!"
    )


def test_format_schema_info():
    assert _format_schema_info(None) == ""
    assert _format_schema_info([]) == ""

    result = _format_schema_info(
        [
            SchemaTable(
                name="df_1",
                columns=[
                    SchemaColumn("age", "int", sample_values=["1", "2"]),
                    SchemaColumn("name", "str", sample_values=[]),
                ],
            )
        ]
    )
    assert "## Available schema:" in result
    assert "- Table: df_1" in result
    assert "- Column: age" in result
    assert "- Type: int" in result
    assert "- Sample values: 1, 2" in result
    # Column without sample values omits the sample line
    assert "- Column: name" in result
    assert "Sample values: \n" not in result


@pytest.mark.parametrize("mode", ["manual", "ask", "agent", "code_mode"])
def test_mode_intro_messages_share_base(mode: CopilotMode):
    message = _get_mode_intro_message(mode)
    assert "You are Marimo Copilot" in message
    assert "reactive programming model" in message


def test_common_chat_sections_empty():
    assert (
        _common_chat_sections(
            custom_rules=None, include_other_code="", context=None
        )
        == ""
    )
    # Whitespace-only custom rules are treated as empty.
    assert (
        _common_chat_sections(
            custom_rules="   ", include_other_code="", context=None
        )
        == ""
    )


def test_common_chat_sections_full():
    result = _common_chat_sections(
        custom_rules="Be concise.",
        include_other_code="import polars as pl",
        context=AiCompletionContext(variables=["var1"]),
    )
    assert "## Additional rules:\nBe concise." in result
    assert "<code_from_other_cells>" in result
    assert "import polars as pl" in result
    assert "## Available variables from other cells:" in result


def test_chat_system_prompt_code_mode():
    prompt = get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=None,
        mode="code_mode",
        session_id=SessionId("s_test"),
    )
    # Code mode uses its own intro and embeds the marimo-pair skill.
    assert _get_mode_intro_message("code_mode") in prompt
    assert "how to work with marimo" in prompt
    assert load_skill("marimo-pair") in prompt
    # Code mode includes single-cell language rules.
    assert "## Rules for python:" in prompt


def test_chat_system_prompt_code_mode_includes_extras():
    prompt = get_chat_system_prompt(
        custom_rules="Always be polite.",
        include_other_code="import pandas as pd\n",
        context=AiCompletionContext(variables=["var1", "var2"]),
        mode="code_mode",
        session_id=SessionId("s_test"),
    )
    assert "## Additional rules:\nAlways be polite." in prompt
    assert "<code_from_other_cells>" in prompt
    assert "import pandas as pd" in prompt
    assert "## Available variables from other cells:" in prompt


def test_chat_system_prompt_non_code_mode_includes_session_info():
    for mode in ("manual", "ask", "agent"):
        prompt = get_chat_system_prompt(
            custom_rules=None,
            include_other_code="",
            context=None,
            mode=cast(CopilotMode, mode),
            session_id=SessionId("s_abc"),
        )
        assert "Current notebook session ID: s_abc" in prompt
        assert "Your goal is to do one of the following two things" in prompt
        # The marimo-pair skill is only embedded in code mode.
        assert "how to work with marimo notebooks" not in prompt


def test_chat_system_prompt_agent_mode_inserts_cell_rules():
    agent_prompt = get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=None,
        mode="agent",
        session_id=SessionId("s_test"),
    )
    manual_prompt = get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=None,
        mode="manual",
        session_id=SessionId("s_test"),
    )
    # Agent mode adds guidance for inserting cells; manual mode does not.
    assert "## Rules for inserting cells:" in agent_prompt
    assert 'mo.md(f"""{content}""")' in agent_prompt
    assert "## Rules for inserting cells:" not in manual_prompt
