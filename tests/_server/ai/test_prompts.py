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
        result += Prompter.get_system_prompt(cast(Language, language))

    result += _header("with custom rules")
    result += Prompter.get_system_prompt(
        "python", custom_rules="Always use type hints."
    )

    snapshot("system_prompts.txt", result)


def test_empty_rules():
    assert Prompter.get_system_prompt("python") == Prompter.get_system_prompt(
        "python",
        custom_rules="  ",
    )


def test_user_prompts():
    prompt = "Create a pandas dataframe"

    result = ""
    result += _header("no code")
    result += Prompter(
        code="", include_other_code="", context=AiCompletionContext()
    ).get_prompt(prompt)

    result += _header("with code")
    result += Prompter(
        code="df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})",
        include_other_code="",
        context=AiCompletionContext(),
    ).get_prompt(prompt)

    result += _header("with code and other code")
    result += Prompter(
        code="df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})",
        include_other_code="import pandas as pd\nimport numpy as np\n",
        context=AiCompletionContext(),
    ).get_prompt(prompt)

    result += _header("with just other code")
    result += Prompter(
        code="",
        include_other_code="import pandas as pd\nimport numpy as np\n",
        context=AiCompletionContext(),
    ).get_prompt(prompt)

    result += _header("with context")
    result += Prompter(
        code="import pandas as pd",
        include_other_code="import marimo as mo",
        context=AiCompletionContext(
            schema=[
                SchemaTable(
                    name="df_1",
                    columns=[
                        SchemaColumn("age", "int"),
                        SchemaColumn("name", "str"),
                    ],
                ),
                SchemaTable(
                    name="d2_2",
                    columns=[
                        SchemaColumn("a", "int"),
                        SchemaColumn("b", "int"),
                    ],
                ),
            ],
        ),
    ).get_prompt(prompt)

    snapshot("user_prompts.txt", result)
