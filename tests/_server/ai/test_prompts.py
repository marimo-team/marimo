# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import cast

from marimo._ast.visitor import Language
from marimo._server.ai.prompts import (
    FILL_ME_TAG,
    _format_variables,
    get_chat_system_prompt,
    get_inline_system_prompt,
    get_refactor_or_insert_notebook_cell_system_prompt,
)
from marimo._server.models.completion import (
    AiCompletionContext,
    SchemaColumn,
    SchemaTable,
    VariableContext,
)
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
        custom_rules="Always use type hints.",
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=None,
    )

    result += _header("with context")
    result += get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
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
        custom_rules=None,
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=None,
    ) == get_refactor_or_insert_notebook_cell_system_prompt(
        language="python",
        is_insert=False,
        custom_rules="  ",
        cell_code=None,
        selected_text=None,
        other_cell_codes=None,
        context=None,
    )


def test_edit_inline_prompts():
    result = get_inline_system_prompt(language="python")
    snapshot("edit_inline_prompts.txt", result)
    # <FILL_ME> is sent from the client, this cannot change without
    # coordination
    assert FILL_ME_TAG in result


def test_chat_system_prompts():
    result: str = ""
    result += _header("no custom rules")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=None,
    )

    result += _header("with custom rules")
    result += get_chat_system_prompt(
        custom_rules="Always be polite.",
        include_other_code="",
        context=None,
    )

    result += _header("with variables")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="",
        context=AiCompletionContext(
            variables=["var1", "var2"],
        ),
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
    )

    result += _header("with other code")
    result += get_chat_system_prompt(
        custom_rules=None,
        include_other_code="import pandas as pd\nimport numpy as np\n",
        context=None,
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
    )

    snapshot("chat_system_prompts.txt", result)


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
