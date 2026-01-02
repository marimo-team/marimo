# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

AiProviderId = NewType("AiProviderId", str)
QualifiedModelId = NewType("QualifiedModelId", str)
ShortModelId = NewType("ShortModelId", str)


@dataclass
class AiModelId:
    provider: AiProviderId
    model: ShortModelId

    def __str__(self) -> QualifiedModelId:
        return QualifiedModelId(f"{self.provider}/{self.model}")

    def __repr__(self) -> str:
        return f"AiModelId(provider={self.provider}, model={self.model})"

    @staticmethod
    def from_model(model_id: str) -> AiModelId:
        if "/" not in model_id:
            LOGGER.warning(
                f"Invalid model ID: {model_id}. Model ID must be in the format <provider>/<model>"
            )
            guess = _guess_provider(model_id)
            LOGGER.warning(f"Guessing provider for {model_id} as {guess}")
            return AiModelId(provider=guess, model=ShortModelId(model_id))

        provider, short_id = model_id.split("/", 1)

        return AiModelId(
            provider=AiProviderId(provider), model=ShortModelId(short_id)
        )


def _guess_provider(model: str) -> AiProviderId:
    def is_google(model: str) -> bool:
        return model.startswith("google") or model.startswith("gemini")

    def is_anthropic(model: str) -> bool:
        return model.startswith("claude")

    def is_openai(model: str) -> bool:
        return (
            model.startswith("gpt")
            or model.startswith("o4")
            or model.startswith("o3")
            or model.startswith("o1")
        )

    if is_google(model):
        return AiProviderId("google")
    elif is_anthropic(model):
        return AiProviderId("anthropic")
    elif is_openai(model):
        return AiProviderId("openai")
    else:
        return AiProviderId("ollama")
