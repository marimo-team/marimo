# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._server.models.completion import (
    AiCompletionContext,
    Language,
)

language_rules = {
    "python": [
        "Do not describe the code, just write the code.",
        "Do not output markdown or backticks.",
        "When using matplotlib to show plots, use plt.gca() instead of plt.show().",
        "If an import already exists, do not import it again.",
        "If a variable is already defined, use another name, or make it private by adding an underscore at the beginning.",
    ],
    "markdown": [],
    "sql": [
        "The SQL must use duckdb syntax.",
    ],
}


class Prompter:
    def __init__(
        self,
        code: str,
        context: Optional[AiCompletionContext],
    ):
        self.code = code
        self.context = context

    @staticmethod
    def get_system_prompt(
        *, language: Language, custom_rules: Optional[str] = None
    ) -> str:
        if language in language_rules:
            all_rules = [f"You can only output {language}."] + language_rules[
                language
            ]
            rules = "\n".join(
                f"{i+1}. {rule}" for i, rule in enumerate(all_rules)
            )
            system_prompt = (
                f"You are a helpful assistant that can answer questions about {language}."
                f" Here are your rules: \n{rules}"
            )

            if custom_rules and custom_rules.strip():
                system_prompt += f"\n\nAdditional rules:\n{custom_rules}"

            return system_prompt
        else:
            return "You are a helpful assistant that can answer questions."

    def get_prompt(self, *, user_prompt: str, include_other_code: str) -> str:
        prompt = user_prompt
        if include_other_code:
            prompt += f"\n\nCode from other cells:\n{include_other_code}"
        if self.code.strip():
            prompt += f"\n\nCurrent code:\n{self.code}"
        if self.context and self.context.schema:
            schema_info = "\n\nAvailable schema:\n"
            for schema in self.context.schema:
                columns = ", ".join(
                    [f"{col.name} ({col.type})" for col in schema.columns]
                )
                schema_info += f"- {schema.name}: {columns}\n"
            prompt += schema_info
        return prompt

    @staticmethod
    def get_chat_system_prompt(
        *,
        custom_rules: Optional[str] = None,
        variables: Optional[list[str]] = None,
        context: Optional[AiCompletionContext] = None,
        include_other_code: str = "",
    ) -> str:
        system_prompt = (
            "You are a helpful assistant working in a marimo notebook. "
            "You can answer questions and help with tasks. "
            "You may respond with markdown, code, or a combination of both. "
            "If you respond in code, you must use the appropriate language block. "
            "And you only work with two languages: Python and SQL. "
            "When responding in code, think of each block of code as a separate cell in the notebook. "
            "The notebook has 2 hard rules: \n"
            "1. Do not import the same library twice. \n"
            "2. Do not define a variable if it already exists. You may reference variables from previous cells, "
            "but you may not define a variable if it already exists. \n"
        )

        for language in language_rules:
            if len(language_rules[language]) == 0:
                continue

            rules = "\n".join(
                f"{i+1}. {rule}"
                for i, rule in enumerate(language_rules[language])
            )

            system_prompt += f"\n\nRules for {language}:\n{rules}"

        if custom_rules and custom_rules.strip():
            system_prompt += f"\n\nAdditional rules:\n{custom_rules}"

        if variables:
            system_prompt += (
                f"\n\nVariables to use but not define:\n{variables}"
            )

        if include_other_code:
            system_prompt += (
                f"\n\nCode from other cells:\n{include_other_code.strip()}"
            )

        if context and context.schema:
            schema_info = "\n\nAvailable schema:\n"
            for schema in context.schema:
                columns = ", ".join(
                    [f"{col.name} ({col.type})" for col in schema.columns]
                )
                schema_info += f"- {schema.name}: {columns}\n"
            system_prompt += schema_info

        return system_prompt
