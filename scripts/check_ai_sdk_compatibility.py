# Copyright 2026 Marimo. All rights reserved.
"""Exercise the pydantic-ai → frontend SDK → marimo chat history boundary.

Run with Python 3.12+ and installed frontend dependencies. No model API or
browser is used. `--requirement minimum|latest|upstream` prints the dependency
constraint for CI. Minimum and latest follow the recommended extra; upstream
keeps its provider extras but tests the newest release without version bounds.
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
    from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def dependency_requirement(
    resolution: Literal["minimum", "latest", "upstream"],
) -> str:
    from packaging.requirements import Requirement

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    requirements = project["project"]["optional-dependencies"]["recommended"]
    requirement = next(
        Requirement(value)
        for value in requirements
        if Requirement(value).name == "pydantic-ai-slim"
    )
    extras = ",".join(sorted(requirement.extras))
    if resolution == "upstream":
        return f"{requirement.name}[{extras}]"
    if resolution == "latest":
        return str(requirement)
    minimum = next(
        spec.version for spec in requirement.specifier if spec.operator == ">="
    )
    return f"{requirement.name}[{extras}]=={minimum}"


Scenario = Literal["completed", "approval", "denied", "error"]


async def check_round_trip(scenario: Scenario) -> None:
    from pydantic import ValidationError
    from pydantic_ai import Agent, DeferredToolRequests, ToolFailed
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

    @agent.tool_plain(requires_approval=scenario in ("approval", "denied"))
    def double(value: int) -> int:
        if scenario == "error":
            raise ToolFailed("Cannot double this value")
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
    request = json.loads(await run_frontend_check(stream, scenario))

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


async def run_frontend_check(payload: str, scenario: str) -> str:
    with tempfile.TemporaryDirectory(
        prefix="marimo-chat-compatibility-"
    ) as tmp:
        input_path = Path(tmp) / "input.txt"
        output_path = Path(tmp) / "history.json"
        input_path.write_text(payload)
        await asyncio.to_thread(
            subprocess.run,
            [
                "node",
                "--experimental-strip-types",
                str(ROOT / "frontend/scripts/check-ai-sdk-compatibility.ts"),
                str(input_path),
                str(output_path),
                scenario,
            ],
            check=True,
            timeout=30,
        )
        return output_path.read_text()


async def check_history_shapes() -> None:
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart
    from pydantic_ai.ui.vercel_ai import VercelAIAdapter

    from marimo._ai._pydantic_ai_utils import convert_to_pydantic_messages

    # Keep wire fixtures independent of backend models so schema gaps stay visible.
    metadata = {"test": {"key": "value"}}
    cases = []
    states: tuple[tuple[str, dict[str, Any]], ...] = (
        ("input-streaming", {}),
        ("input-available", {}),
        ("output-available", {"output": 4}),
        ("output-error", {"errorText": "Tool failed"}),
        ("approval-requested", {"approval": {"id": "approve"}}),
        (
            "approval-responded",
            {"approval": {"id": "approve", "approved": True}},
        ),
        (
            "approval-responded",
            {
                "approval": {
                    "id": "approve",
                    "approved": False,
                    "reason": "Declined",
                }
            },
        ),
        (
            "output-denied",
            {
                "approval": {
                    "id": "approve",
                    "approved": False,
                    "reason": "Declined",
                }
            },
        ),
    )
    for dynamic in (False, True):
        for index, (state, fields) in enumerate(states):
            name = f"{'dynamic' if dynamic else 'static'}-{state}-{index}"
            part = {
                "type": "dynamic-tool" if dynamic else "tool-double",
                "toolCallId": name,
                "state": state,
                "input": {"value": 2},
                "title": "Double",
                "providerExecuted": False,
                "callProviderMetadata": metadata,
                **fields,
            }
            if dynamic:
                part["toolName"] = "double"
            cases.append(
                {
                    "name": name,
                    "messages": [
                        {
                            "id": "user",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Double two"}],
                        },
                        {
                            "id": "assistant",
                            "role": "assistant",
                            "parts": [part],
                        },
                    ],
                }
            )
    cases.append(
        {
            "name": "content-and-context",
            "messages": [
                {
                    "id": "user",
                    "role": "user",
                    "metadata": {"request": "fixture"},
                    "parts": [
                        {
                            "type": "text",
                            "text": "Inspect this file",
                            "state": "done",
                            "providerMetadata": metadata,
                        },
                        {
                            "type": "file",
                            "mediaType": "image/png",
                            "filename": "pixel.png",
                            "url": "data:image/png;base64,iVBORw0KGgo=",
                            "providerMetadata": metadata,
                        },
                        {
                            "type": "data-marimo-context",
                            "data": {"plainText": "Cell context"},
                        },
                    ],
                },
                {
                    "id": "assistant",
                    "role": "assistant",
                    "parts": [
                        {"type": "step-start"},
                        {
                            "type": "file",
                            "mediaType": "text/plain",
                            "filename": "answer.txt",
                            "url": "data:text/plain;base64,RG9uZQ==",
                            "providerMetadata": metadata,
                        },
                        {
                            "type": "reasoning",
                            "id": "reasoning",
                            "text": "Inspecting",
                            "state": "done",
                            "providerMetadata": metadata,
                        },
                        {
                            "type": "source-url",
                            "sourceId": "url",
                            "url": "https://example.com/",
                            "title": "Reference",
                            "providerMetadata": metadata,
                        },
                        {
                            "type": "source-document",
                            "sourceId": "doc",
                            "mediaType": "text/plain",
                            "title": "Document",
                            "filename": "doc.txt",
                            "providerMetadata": metadata,
                        },
                        {
                            "type": "text",
                            "text": "Done",
                            "state": "done",
                            "providerMetadata": metadata,
                        },
                    ],
                },
            ],
        }
    )
    histories = json.loads(
        await run_frontend_check(json.dumps(cases), "history")
    )
    assert len(histories) == len(cases), "The SDK omitted a history fixture"
    for history in histories:
        name = history["name"]
        try:
            messages = convert_to_pydantic_messages(history["messages"])
            loaded = VercelAIAdapter.load_messages(messages)
            assert loaded, f"{name}: the adapter discarded history"
            if name != "content-and-context":
                calls = [
                    part
                    for message in loaded
                    for part in message.parts
                    if isinstance(part, ToolCallPart)
                ]
                assert len(calls) == 1, f"{name}: tool call was lost"
                assert calls[0].tool_name == "double"
                assert calls[0].args_as_dict() == {"value": 2}
                assert calls[0].tool_call_id == name
                if "approval-" not in name:
                    results = [
                        part
                        for message in loaded
                        for part in message.parts
                        if isinstance(part, ToolReturnPart)
                    ]
                    assert len(results) == 1, f"{name}: tool result was lost"
                    assert results[0].tool_call_id == name
                    if "output-available" in name:
                        assert results[0].content == 4
                    elif "output-error" in name:
                        assert results[0].content == "Tool failed"
                    elif "output-denied" in name:
                        assert results[0].outcome == "denied"
                    else:
                        assert "interrupted" in str(results[0].content).lower()
            else:
                assert messages[0].metadata == {"request": "fixture"}
                assert any(
                    "Cell context" in getattr(part, "text", "")
                    for part in messages[0].parts
                )
        except Exception as exc:
            raise RuntimeError(
                f"History fixture {name} failed with pydantic-ai-slim={version('pydantic-ai-slim')}"
            ) from exc
        sys.stdout.write(f"{name}: frontend history is compatible\n")


async def check_compatibility() -> None:
    sys.stdout.write(
        f"Checking pydantic-ai-slim={version('pydantic-ai-slim')}\n"
    )
    sys.stdout.flush()
    scenarios: tuple[Scenario, ...] = (
        "completed",
        "approval",
        "denied",
        "error",
    )
    for scenario in scenarios:
        await check_round_trip(scenario)
    await check_history_shapes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirement", choices=("minimum", "latest", "upstream")
    )
    args = parser.parse_args()
    if args.requirement:
        sys.stdout.write(f"{dependency_requirement(args.requirement)}\n")
    else:
        asyncio.run(check_compatibility())


if __name__ == "__main__":
    main()
