# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._server.models.completion import (
    AiCompletionContext,
    Language,
)

language_rules = {
    "python": [
        "When using matplotlib to show plots, use plt.gca() instead of plt.show().",
        "If an import already exists, do not import it again.",
        "If a variable is already defined, use another name, or make it private by adding an underscore at the beginning.",
    ],
    "markdown": [],
    "sql": [
        "The SQL must use duckdb syntax.",
    ],
}


def _format_schema_info(context: Optional[AiCompletionContext]) -> str:
    """Helper to format schema information from context"""
    if not context or not context.schema:
        return ""

    schema_info = "\n\nAvailable schema:\n"
    for schema in context.schema:
        schema_info += f"- Table: {schema.name}\n"
        for col in schema.columns:
            schema_info += f"  - Column: {col.name}\n"
            schema_info += f"    - Type: {col.type}\n"
            if col.sample_values:
                samples = ", ".join(f"{v}" for v in col.sample_values)
                schema_info += f"    - Sample values: {samples}\n"
    return schema_info


class Prompter:
    def __init__(self, code: str):
        self.code = code

    @staticmethod
    def get_system_prompt(
        *,
        language: Language,
        custom_rules: Optional[str] = None,
        context: Optional[AiCompletionContext] = None,
    ) -> str:
        if language in language_rules:
            all_rules = [
                "Do not describe the code, just write the code.",
                "Do not output markdown or backticks.",
            ] + language_rules[language]
            rules = "\n".join(
                f"{i+1}. {rule}" for i, rule in enumerate(all_rules)
            )
            system_prompt = (
                f"You are a helpful assistant that can answer questions about {language}."
                f" Here are your rules: \n{rules}"
            )

            if custom_rules and custom_rules.strip():
                system_prompt += f"\n\nAdditional rules:\n{custom_rules}"
        else:
            system_prompt = (
                "You are a helpful assistant that can answer questions."
            )

        system_prompt += _format_schema_info(context)

        return system_prompt

    def get_prompt(self, *, user_prompt: str, include_other_code: str) -> str:
        prompt = user_prompt
        if include_other_code:
            prompt += f"\n\n<code-from-other-cells>\n{include_other_code.strip()}\n</code-from-other-cells>"
        if self.code.strip():
            prompt += (
                f"\n\n<current-code>\n{self.code.strip()}\n</current-code>"
            )
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

        system_prompt += _format_schema_info(context)

        return system_prompt
