from __future__ import annotations

import base64
import difflib
import hashlib
import inspect
import json
import math
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from benchmarks.ai.models import (
    CheckResult,
    ExpectedValue,
    FileAttachment,
    HarnessVariant,
    JSONValue,
    NumericExpectation,
    Scenario,
    ScenarioResult,
    ScenarioWorkspace,
    TokenUsage,
    ToolCallMetrics,
    TurnMetrics,
)
from benchmarks.ai.server import MarimoServer
from benchmarks.ai.vercel_stream import serialized_chars

if TYPE_CHECKING:
    from collections.abc import Callable


def logfire_run_query(run_id: str) -> str:
    """Return the Logfire filter that selects every turn in an eval run."""
    return f"attributes->>'marimo.ai.eval.run_id' = '{run_id}'"


def _message(
    role: str,
    text: str,
    attachments: tuple[FileAttachment, ...] = (),
) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for attachment in attachments:
        encoded = base64.b64encode(attachment.path.read_bytes()).decode()
        parts.append(
            {
                "type": "file",
                "mediaType": attachment.media_type,
                "filename": attachment.filename,
                "url": f"data:{attachment.media_type};base64,{encoded}",
            }
        )
    return {
        "id": f"{role}-{uuid.uuid4().hex[:12]}",
        "role": role,
        "parts": parts,
    }


def _compare_summary(
    actual: dict[str, Any], expected: dict[str, ExpectedValue]
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for key, expected_value in expected.items():
        if key not in actual:
            checks.append(
                CheckResult(key, False, "Missing from analysis_summary")
            )
            continue
        actual_value = actual[key]
        expected_display: JSONValue
        if isinstance(expected_value, NumericExpectation):
            expected_display = expected_value.value
            try:
                passed = math.isclose(
                    float(actual_value),
                    float(expected_value.value),
                    rel_tol=0,
                    abs_tol=expected_value.absolute_tolerance,
                )
            except (TypeError, ValueError):
                passed = False
        elif isinstance(expected_value, (int, float)) and not isinstance(
            expected_value, bool
        ):
            expected_display = expected_value
            try:
                passed = math.isclose(
                    float(actual_value),
                    float(expected_value),
                    rel_tol=1e-6,
                    abs_tol=1e-6,
                )
            except (TypeError, ValueError):
                passed = False
        else:
            expected_display = expected_value
            passed = (
                str(actual_value).casefold() == str(expected_value).casefold()
            )
        checks.append(
            CheckResult(
                key,
                passed,
                f"expected {expected_display!r}; got {actual_value!r}",
            )
        )
    return checks


def _marimo_check(notebook: Path) -> CheckResult:
    process = subprocess.run(
        [sys.executable, "-m", "marimo", "check", str(notebook)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    detail = (process.stdout + process.stderr).strip()
    return CheckResult(
        "marimo_check",
        process.returncode == 0,
        detail or f"exit code {process.returncode}",
    )


def _source_contract_checks(
    source: str,
    workspace: ScenarioWorkspace,
) -> list[CheckResult]:
    checks = [
        CheckResult(
            name=f"source_contains:{fragment}",
            passed=fragment in source,
            reason=f"required notebook source fragment: {fragment!r}",
        )
        for fragment in workspace.required_source_fragments
    ]
    checks.extend(
        CheckResult(
            name=f"source_matches:{pattern}",
            passed=re.search(pattern, source) is not None,
            reason=f"required notebook source pattern: {pattern!r}",
        )
        for pattern in workspace.required_source_patterns
    )
    checks.extend(
        CheckResult(
            name=f"source_excludes:{fragment}",
            passed=fragment not in source,
            reason=f"forbidden notebook source fragment: {fragment!r}",
        )
        for fragment in workspace.forbidden_source_fragments
    )
    checks.extend(
        CheckResult(
            name=f"source_order:{before}->{after}",
            passed=(
                before in source
                and after in source
                and source.index(before) < source.index(after)
            ),
            reason=f"{before!r} must appear before {after!r}",
        )
        for before, after in workspace.required_source_order
    )
    return checks


def run_scenario(
    scenario: Scenario,
    *,
    model: str,
    variant: HarnessVariant,
    repetition: int,
    output_dir: Path,
    timeout_seconds: float,
    on_turn: Callable[[TurnMetrics, int], None] | None = None,
) -> ScenarioResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(
        prefix=f"marimo-eval-{scenario.id}-"
    ) as temp:
        root = Path(temp)
        workspace = scenario.setup(root)
        before = workspace.notebook.read_text(encoding="utf-8")
        responses: list[str] = []
        trace_ids: list[str] = []
        trial_id = f"{scenario.id}-{variant.id}-r{repetition:03d}"
        conversation_id = f"eval-{output_dir.name}-{trial_id}"
        error: str | None = None
        checks: list[CheckResult] = []
        observed_summary: dict[str, JSONValue] = {}
        turn_metrics: list[TurnMetrics] = []
        tool_calls = 0
        tool_errors = 0
        usage = TokenUsage()
        try:
            with MarimoServer(
                root=root,
                notebook=workspace.notebook,
                model=model,
                timeout_seconds=timeout_seconds,
                eval_run_id=output_dir.name,
                scenario_id=scenario.id,
                trial_id=trial_id,
                repetition=repetition,
                variant=variant,
                session_id=conversation_id,
                isolated_environment=scenario.isolated_environment,
            ) as server:
                messages: list[dict[str, Any]] = []

                def send_turn(
                    turn: str, turn_number: int, total_turns: int
                ) -> None:
                    nonlocal usage
                    nonlocal tool_calls
                    nonlocal tool_errors
                    for edit in scenario.live_cell_edits:
                        if edit.before_turn == turn_number:
                            server.edit_cell(edit.cell_name, edit.code)
                    messages.append(
                        _message(
                            "user",
                            turn,
                            workspace.turn_attachments.get(turn_number, ()),
                        )
                    )
                    request_history_chars = serialized_chars(messages)
                    turn_started = time.monotonic()
                    chat_turn = server.chat(messages, turn_number=turn_number)
                    if chat_turn.trace_id:
                        trace_ids.append(chat_turn.trace_id)
                    messages.append(chat_turn.message)
                    responses.append(chat_turn.text)
                    tool_calls += chat_turn.tool_calls
                    tool_errors += chat_turn.tool_errors
                    usage += chat_turn.usage
                    metrics = TurnMetrics(
                        turn_number=turn_number,
                        trace_id=chat_turn.trace_id,
                        duration_seconds=time.monotonic() - turn_started,
                        tool_calls=chat_turn.tool_calls,
                        tool_errors=chat_turn.tool_errors,
                        usage=chat_turn.usage,
                        response_chars=len(chat_turn.text),
                        request_history_chars=request_history_chars,
                        effective_history_chars=(
                            chat_turn.effective_history_chars
                        ),
                        assistant_message_chars=serialized_chars(
                            chat_turn.message
                        ),
                        tool_metrics=chat_turn.tool_metrics,
                    )
                    turn_metrics.append(metrics)
                    if on_turn is not None:
                        on_turn(metrics, total_turns)

                for turn_number, turn in enumerate(scenario.turns, start=1):
                    send_turn(turn, turn_number, len(scenario.turns))

                actual_summary = server.inspect_summary()
                observed_summary = actual_summary
                checks.extend(
                    _compare_summary(
                        actual_summary, workspace.expected_summary
                    )
                )
            final_source = workspace.notebook.read_text(encoding="utf-8")
            checks.extend(_source_contract_checks(final_source, workspace))
            checks.append(_marimo_check(workspace.notebook))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        after = workspace.notebook.read_text(encoding="utf-8")
        result = ScenarioResult(
            trial_id=trial_id,
            scenario_id=scenario.id,
            scenario_length=scenario.length,
            failure_modes=scenario.failure_modes,
            variant_id=variant.id,
            repetition=repetition,
            model=model,
            conversation_id=conversation_id,
            trace_ids=trace_ids,
            duration_seconds=time.monotonic() - started,
            observed_summary=observed_summary,
            checks=checks,
            assistant_responses=responses,
            turn_metrics=turn_metrics,
            turns_completed=len(responses),
            tool_calls=tool_calls,
            tool_errors=tool_errors,
            usage=usage,
            error=error,
        )
        _write_trial_artifacts(
            output_dir=output_dir,
            scenario=scenario,
            result=result,
            before=before,
            after=after,
            workspace_root=root,
        )
        return result


def _write_trial_artifacts(
    *,
    output_dir: Path,
    scenario: Scenario,
    result: ScenarioResult,
    before: str,
    after: str,
    workspace_root: Path,
) -> None:
    trial_dir = (
        output_dir
        / "trials"
        / scenario.id
        / result.variant_id
        / f"repetition-{result.repetition:03d}"
    )
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "result.json").write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    (trial_dir / "notebook.before.py").write_text(before, encoding="utf-8")
    (trial_dir / "notebook.after.py").write_text(after, encoding="utf-8")
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="notebook.before.py",
        tofile="notebook.after.py",
    )
    (trial_dir / "notebook.diff").write_text("".join(diff), encoding="utf-8")
    server_log = workspace_root / "marimo-server.log"
    if server_log.exists():
        shutil.copy2(server_log, trial_dir / "marimo-server.log")


def create_run_directory(
    base: Path,
    model: str,
    scenarios: tuple[Scenario, ...],
    variants: tuple[HarnessVariant, ...],
    repetitions: int,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = base / f"{timestamp}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True)
    scenario_source_files = {
        Path(source_file).resolve()
        for scenario in scenarios
        if (source_file := inspect.getsourcefile(scenario.setup)) is not None
    }
    scenario_hash = hashlib.sha256(
        (
            "\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted(scenario_source_files)
            )
            + "\n"
            + "\n".join(
                "\n".join(
                    (
                        scenario.id,
                        scenario.description,
                        scenario.length,
                        *scenario.failure_modes,
                        *scenario.turns,
                        str(scenario.isolated_environment),
                        str(scenario.requires_vision),
                        *(repr(edit) for edit in scenario.live_cell_edits),
                        inspect.getsource(scenario.setup),
                    )
                )
                for scenario in scenarios
            )
        ).encode()
    ).hexdigest()
    try:
        git_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:
        git_sha = ""
    manifest = {
        "schema_version": 4,
        "run_id": run_dir.name,
        "logfire_query": logfire_run_query(run_dir.name),
        "model": model,
        "variants": [asdict(variant) for variant in variants],
        "repetitions": repetitions,
        "scenario_ids": [scenario.id for scenario in scenarios],
        "scenario_hash": scenario_hash,
        "git_sha": git_sha,
        "python_version": platform.python_version(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return run_dir


def write_summary(run_dir: Path, results: list[ScenarioResult]) -> None:
    def metrics(trials: list[ScenarioResult]) -> dict[str, JSONValue]:
        durations = [trial.duration_seconds for trial in trials]
        total_usage = sum(
            (trial.usage for trial in trials), start=TokenUsage()
        )
        turn_metrics = [
            turn for trial in trials for turn in trial.turn_metrics
        ]
        tool_metrics: list[ToolCallMetrics] = [
            tool for turn in turn_metrics for tool in turn.tool_metrics
        ]
        tool_payloads: dict[str, dict[str, int]] = {}
        for tool in tool_metrics:
            payload = tool_payloads.setdefault(
                tool.name,
                {"calls": 0, "input_chars": 0, "output_chars": 0},
            )
            payload["calls"] += 1
            payload["input_chars"] += tool.input_chars
            payload["output_chars"] += tool.output_chars
        return {
            "trials": len(trials),
            "passed": sum(trial.passed for trial in trials),
            "pass_rate": sum(trial.passed for trial in trials) / len(trials),
            "mean_duration_seconds": statistics.mean(durations),
            "duration_stddev_seconds": statistics.pstdev(durations),
            "mean_tool_calls": statistics.mean(
                trial.tool_calls for trial in trials
            ),
            "mean_tool_errors": statistics.mean(
                trial.tool_errors for trial in trials
            ),
            "total_model_requests": total_usage.requests,
            "mean_model_requests": total_usage.requests / len(trials),
            "total_input_tokens": total_usage.input_tokens,
            "mean_input_tokens": total_usage.input_tokens / len(trials),
            "total_output_tokens": total_usage.output_tokens,
            "mean_output_tokens": total_usage.output_tokens / len(trials),
            "total_reasoning_tokens": total_usage.reasoning_tokens,
            "mean_reasoning_tokens": total_usage.reasoning_tokens
            / len(trials),
            "total_cache_read_tokens": total_usage.cache_read_tokens,
            "mean_cache_read_tokens": total_usage.cache_read_tokens
            / len(trials),
            "total_cache_write_tokens": total_usage.cache_write_tokens,
            "mean_cache_write_tokens": total_usage.cache_write_tokens
            / len(trials),
            "total_request_history_chars": sum(
                turn.request_history_chars for turn in turn_metrics
            ),
            "mean_final_request_history_chars": statistics.mean(
                trial.turn_metrics[-1].request_history_chars
                if trial.turn_metrics
                else 0
                for trial in trials
            ),
            "total_effective_history_chars": sum(
                turn.effective_history_chars for turn in turn_metrics
            ),
            "mean_final_effective_history_chars": statistics.mean(
                trial.turn_metrics[-1].effective_history_chars
                if trial.turn_metrics
                else 0
                for trial in trials
            ),
            "total_assistant_message_chars": sum(
                turn.assistant_message_chars for turn in turn_metrics
            ),
            "total_tool_input_chars": sum(
                tool.input_chars for tool in tool_metrics
            ),
            "total_tool_output_chars": sum(
                tool.output_chars for tool in tool_metrics
            ),
            "tool_payloads": cast(JSONValue, tool_payloads),
        }

    scenario_groups: dict[tuple[str, str], list[ScenarioResult]] = {}
    variant_groups: dict[str, list[ScenarioResult]] = {}
    length_groups: dict[tuple[str, str], list[ScenarioResult]] = {}
    for result in results:
        scenario_groups.setdefault(
            (result.scenario_id, result.variant_id), []
        ).append(result)
        variant_groups.setdefault(result.variant_id, []).append(result)
        length_groups.setdefault(
            (result.scenario_length, result.variant_id), []
        ).append(result)

    scenario_aggregates = [
        {
            "scenario_id": scenario_id,
            "variant_id": variant_id,
            **metrics(trials),
        }
        for (scenario_id, variant_id), trials in sorted(
            scenario_groups.items()
        )
    ]
    variant_aggregates = [
        {"variant_id": variant_id, **metrics(trials)}
        for variant_id, trials in sorted(variant_groups.items())
    ]
    length_aggregates = [
        {
            "scenario_length": scenario_length,
            "variant_id": variant_id,
            **metrics(trials),
        }
        for (scenario_length, variant_id), trials in sorted(
            length_groups.items()
        )
    ]
    summary = {
        "run_id": run_dir.name,
        "logfire_query": logfire_run_query(run_dir.name),
        "passed": all(result.passed for result in results),
        "scenario_aggregates": scenario_aggregates,
        "variant_aggregates": variant_aggregates,
        "length_aggregates": length_aggregates,
        "cases": [result.to_dict() for result in results],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
