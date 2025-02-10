# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import cast

from marimo._ast.visitor import Language
from marimo._server.ai.prompts import Prompter
from marimo._server.models.completion import (
    AiCompletionContext,
    SchemaColumn,
    SchemaTable,
)
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def _header(title: str) -> str:
    return f"\n\n==================== {title} ====================\n\n"


def test_system_prompts():
    result = ""
    for language in ("python", "markdown", "sql", "idk"):
        result += _header(language)
        result += Prompter.get_system_prompt(language=cast(Language, language))

    result += _header("with custom rules")
    result += Prompter.get_system_prompt(
        language="python", custom_rules="Always use type hints."
    )

    result += _header("with context")
    result += Prompter.get_system_prompt(
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
    )

    snapshot("system_prompts.txt", result)


def test_empty_rules():
    assert Prompter.get_system_prompt(
        language="python"
    ) == Prompter.get_system_prompt(
        language="python",
        custom_rules="  ",
    )


def test_user_prompts():
    prompt = "Create a pandas dataframe"

    result: str = ""
    result += _header("no code")
    result += Prompter(code="").get_prompt(
        user_prompt=prompt, include_other_code=""
    )

    result += _header("with code")
    result += Prompter(
        code="df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})",
    ).get_prompt(user_prompt=prompt, include_other_code="")

    result += _header("with code and other code")
    result += Prompter(
        code="df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})",
    ).get_prompt(
        user_prompt=prompt,
        include_other_code="import pandas as pd\nimport numpy as np\n",
    )

    result += _header("with just other code")
    result += Prompter(
        code="",
    ).get_prompt(
        user_prompt=prompt,
        include_other_code="import pandas as pd\nimport numpy as np\n",
    )

    result += _header("with context")
    result += Prompter(code="import pandas as pd").get_prompt(
        user_prompt=prompt, include_other_code="import marimo as mo"
    )

    snapshot("user_prompts.txt", result)


def test_edit_inline_prompts():
    # Nothing fancy here, just making sure
    # that if we already give a fully formatted prompt without
    # any code, we don't add any more instructions
    prompt = """
    Given the following code context, {opts.prompt}

    SELECTED CODE:
    {opts.selection}

    Instructions:
    1. Modify ONLY the selected code`;
    """

    result = Prompter(code="").get_prompt(
        user_prompt=prompt,
        include_other_code="",
    )

    assert result == prompt


def test_chat_system_prompts():
    result: str = ""
    result += _header("no custom rules")
    result += Prompter.get_chat_system_prompt()

    result += _header("with custom rules")
    result += Prompter.get_chat_system_prompt(custom_rules="Always be polite.")

    result += _header("with variables")
    result += Prompter.get_chat_system_prompt(variables=["var1", "var2"])

    result += _header("with context")
    result += Prompter.get_chat_system_prompt(
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
        )
    )

    result += _header("with other code")
    result += Prompter.get_chat_system_prompt(
        include_other_code="import pandas as pd\nimport numpy as np\n"
    )

    result += _header("kitchen sink")
    result += Prompter.get_chat_system_prompt(
        custom_rules="Always be polite.",
        variables=["var1", "var2"],
        include_other_code="import pandas as pd\nimport numpy as np\n",
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
            ],
        ),
    )

    snapshot("chat_system_prompts.txt", result)
