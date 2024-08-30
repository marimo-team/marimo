# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._server.models.completion import AiCompletionContext, Language


class Prompter:
    def __init__(
        self,
        code: str,
        include_other_code: str,
        context: Optional[AiCompletionContext],
    ):
        self.code = code
        self.include_other_code = include_other_code
        self.context = context

    @staticmethod
    def get_system_prompt(language: Language) -> str:
        language_rules = {
            "python": [
                "You can only output python code.",
                "Do not describe the code, just write the code.",
                "Do not output markdown or backticks.",
                "When using matplotlib to show plots, use plt.gca() instead of plt.show().",  # noqa: E501
                "If an import already exists, do not import it again.",
                "If a variable is already defined, use another name, or make it private by adding an underscore at the beginning.",  # noqa: E501
            ],
            "markdown": ["You can only output markdown."],
            "sql": [
                "You can only output sql.",
                "The SQL must use duckdb syntax.",
            ],
        }

        if language in language_rules:
            rules = "\n".join(
                f"{i+1}. {rule}"
                for i, rule in enumerate(language_rules[language])
            )
            return (
                f"You are a helpful assistant that can answer questions about {language}."  # noqa: E501
                f" Here are your rules: \n{rules}"
            )
        else:
            return "You are a helpful assistant that can answer questions."

    def get_prompt(self, user_prompt: str) -> str:
        prompt = user_prompt
        if self.include_other_code:
            prompt += f"\n\nCode from other cells:\n{self.include_other_code}"
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
