# Copyright 2026 Marimo. All rights reserved.
"""Exercise the pydantic-ai → frontend SDK → marimo chat history boundary.

Run with Python 3.12+ and installed frontend dependencies. No model API or
browser is used. `--requirement minimum|latest` prints the dependency constraint
for CI, deriving both cases from the recommended extra in pyproject.toml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import tomllib

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

ROOT = Path(__file__).resolve().parent.parent


def dependency_requirement(resolution: Literal["minimum", "latest"]) -> str:
    from packaging.requirements import Requirement

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    requirements = project["project"]["optional-dependencies"]["recommended"]
    requirement = next(
        Requirement(value)
        for value in requirements
        if Requirement(value).name == "pydantic-ai-slim"
    )
    if resolution == "latest":
        return str(requirement)
    minimum = next(
        spec.version for spec in requirement.specifier if spec.operator == ">="
    )
    extras = ",".join(sorted(requirement.extras))
    return f"{requirement.name}[{extras}]=={minimum}"


async def check_round_trip(scenario: Literal["completed", "approval"]) -> None:
    from pydantic import ValidationError
    from pydantic_ai import Agent, DeferredToolRequests
    from pydantic_ai.messages import ModelMessage, ToolReturnPart
    from pydantic_ai.models.function import (
        AgentInfo,
        DeltaThinkingCalls,
        DeltaThinkingPart,
        DeltaToolCall,
        DeltaToolCalls,
        FunctionModel,
    )
    from pydantic_ai.ui.vercel_ai import VercelAIAdapter
    from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

    from marimo._ai._pydantic_ai_utils import convert_to_pydantic_messages
    from marimo._plugins.ui._impl.chat.chat import AI_SDK_VERSION

    async def respond(
        messages: list[ModelMessage], _info: AgentInfo
    ) -> AsyncIterator[str | DeltaThinkingCalls | DeltaToolCalls]:
        if any(
            isinstance(part, ToolReturnPart) for part in messages[-1].parts
        ):
            yield "The answer is four."
        else:
            yield {0: DeltaThinkingPart(content="I will double two.")}
            yield {
                1: DeltaToolCall(
                    name="double",
                    json_args='{"value": 2}',
                    tool_call_id="double-call",
                )
            }

    agent = Agent(
        FunctionModel(stream_function=respond),
        output_type=[str, DeferredToolRequests],
    )

    @agent.tool_plain(requires_approval=scenario == "approval")
    def double(value: int) -> int:
        return value * 2

    adapter = VercelAIAdapter(
        agent=agent,
        run_input=SubmitMessage(
            id="compatibility-chat",
            trigger="submit-message",
            messages=convert_to_pydantic_messages(
                [
                    {
                        "id": "user-1",
                        "role": "user",
                        "parts": [{"type": "text", "text": "Double two"}],
                    }
                ]
            ),
        ),
        sdk_version=AI_SDK_VERSION,
    )
    stream = "".join(
        [chunk async for chunk in adapter.encode_stream(adapter.run_stream())]
    )
    with tempfile.TemporaryDirectory(
        prefix="marimo-chat-compatibility-"
    ) as tmp:
        stream_path = Path(tmp) / "stream.txt"
        history_path = Path(tmp) / "history.json"
        stream_path.write_text(stream)
        await asyncio.to_thread(
            subprocess.run,
            [
                "node",
                str(ROOT / "frontend/scripts/check-ai-sdk-compatibility.ts"),
                str(stream_path),
                str(history_path),
                scenario,
            ],
            check=True,
            timeout=30,
        )
        request = json.loads(history_path.read_text())

    try:
        messages = convert_to_pydantic_messages(request["messages"])
        model_messages = VercelAIAdapter.load_messages(messages)
    except ValidationError as exc:
        raise RuntimeError(
            f"Chat protocol incompatibility ({scenario}): "
            f"pydantic-ai-slim={version('pydantic-ai-slim')} rejected "
            f"the frontend SDK's second-turn history:\n{exc}"
        ) from exc
    assert model_messages, "The adapter discarded the chat history"
    assert any(message.role == "assistant" for message in messages)
    sys.stdout.write(
        f"{scenario}: stream and second-turn history are compatible\n"
    )


async def check_compatibility() -> None:
    sys.stdout.write(
        f"Checking pydantic-ai-slim={version('pydantic-ai-slim')}\n"
    )
    sys.stdout.flush()
    scenarios: tuple[Literal["completed", "approval"], ...] = (
        "completed",
        "approval",
    )
    for scenario in scenarios:
        await check_round_trip(scenario)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirement", choices=("minimum", "latest"))
    args = parser.parse_args()
    if args.requirement:
        sys.stdout.write(f"{dependency_requirement(args.requirement)}\n")
    else:
        asyncio.run(check_compatibility())


if __name__ == "__main__":
    main()
