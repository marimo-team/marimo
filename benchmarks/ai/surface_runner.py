from __future__ import annotations

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from benchmarks.ai.models import (
    CheckResult,
    ExpectedValue,
    HarnessVariant,
    JSONValue,
    TokenUsage,
)
from benchmarks.ai.runner import _compare_summary, logfire_run_query, model_key
from benchmarks.ai.server import HttpRequestError, MarimoServer
from benchmarks.ai.surface_models import (
    GenerateScenario,
    GenerateWorkspace,
    InlineScenario,
    SurfaceResult,
)

_SUMMARY_MARKER = "__MARIMO_AI_SURFACE_EVAL__"
_SURFACE_VARIANT = HarnessVariant(
    id="surface",
    description="Production endpoint without a chat harness variant.",
)
_ZERO_USAGE = TokenUsage()


def _trim_inline_response(response: str, prefix: str, suffix: str) -> str:
    """Mirror the editor's exact-prefix and exact-suffix cleanup."""
    trimmed = response
    if prefix and trimmed.startswith(prefix):
        trimmed = trimmed[len(prefix) :]
    if suffix and trimmed.endswith(suffix):
        trimmed = trimmed[: -len(suffix)]
    return trimmed


def _evaluate_python(
    source: str,
    expected: dict[str, ExpectedValue],
    *,
    root: Path,
) -> list[CheckResult]:
    try:
        compile(source, "<ai-surface-candidate>", "exec")
    except SyntaxError as exc:
        return [CheckResult("python_syntax", False, str(exc))]

    candidate = root / "surface-candidate.py"
    candidate.write_text(
        source
        + "\n\nimport json as _marimo_eval_json\n"
        + f"print({_SUMMARY_MARKER!r} + _marimo_eval_json.dumps("
        + "analysis_summary, sort_keys=True, default=str))\n",
        encoding="utf-8",
    )
    process = subprocess.run(
        [sys.executable, str(candidate)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if process.returncode != 0:
        detail = (process.stdout + process.stderr).strip()
        return [CheckResult("python_execution", False, detail[-4000:])]
    if _SUMMARY_MARKER not in process.stdout:
        return [
            CheckResult(
                "analysis_summary",
                False,
                "Generated code did not define analysis_summary",
            )
        ]
    payload = process.stdout.rsplit(_SUMMARY_MARKER, 1)[1].splitlines()[0]
    summary = json.loads(payload)
    if not isinstance(summary, dict):
        return [
            CheckResult(
                "analysis_summary",
                False,
                "analysis_summary was not a dictionary",
            )
        ]
    return [
        CheckResult("python_execution", True, "candidate executed"),
        *_compare_summary(summary, expected),
    ]


def _generate_checks(
    cells: tuple[dict[str, str], ...],
    workspace: GenerateWorkspace,
    *,
    root: Path,
) -> tuple[list[CheckResult], str]:
    python_cells = [
        cell["code"] for cell in cells if cell["language"] == "python"
    ]
    checks = [
        CheckResult(
            "minimum_python_cells",
            len(python_cells) >= workspace.minimum_python_cells,
            "expected at least "
            f"{workspace.minimum_python_cells}; got {len(python_cells)}",
        )
    ]
    if workspace.maximum_python_cells is not None:
        checks.append(
            CheckResult(
                "maximum_python_cells",
                len(python_cells) <= workspace.maximum_python_cells,
                "expected at most "
                f"{workspace.maximum_python_cells}; got {len(python_cells)}",
            )
        )
    generated_source = "\n\n".join(python_cells)
    checks.extend(
        CheckResult(
            f"source_matches:{pattern}",
            re.search(pattern, generated_source) is not None,
            f"required generated-source pattern: {pattern!r}",
        )
        for pattern in workspace.required_source_patterns
    )
    checks.extend(
        CheckResult(
            f"source_excludes_pattern:{pattern}",
            re.search(pattern, generated_source) is None,
            f"forbidden generated-source pattern: {pattern!r}",
        )
        for pattern in workspace.forbidden_source_patterns
    )
    executable_source = "\n\n".join(
        part for part in (workspace.prelude, generated_source) if part
    )
    checks.extend(
        _evaluate_python(
            executable_source,
            workspace.expected_summary,
            root=root,
        )
    )
    return checks, executable_source


def run_generate_scenario(
    scenario: GenerateScenario,
    *,
    model: str,
    repetition: int,
    output_dir: Path,
    timeout_seconds: float,
) -> SurfaceResult:
    started = time.monotonic()
    trial_id = f"{scenario.id}-generate-{model_key(model)}-r{repetition:03d}"
    with tempfile.TemporaryDirectory(
        prefix=f"marimo-eval-{scenario.id}-"
    ) as temp:
        root = Path(temp)
        workspace = scenario.setup(root)
        response: JSONValue = None
        checks: list[CheckResult] = []
        error: str | None = None
        trace_id = ""
        source = ""
        usage = _ZERO_USAGE
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
                variant=_SURFACE_VARIANT,
                session_id=f"eval-{output_dir.name}-{trial_id}",
            ) as server:
                turn = server.generate(
                    workspace.prompt,
                    include_other_code=workspace.include_other_code,
                    context_plain_text=workspace.context_plain_text,
                )
                trace_id = turn.trace_id
                usage = turn.usage
                response = [dict(cell) for cell in turn.cells]
                checks, source = _generate_checks(
                    turn.cells, workspace, root=root
                )
        except Exception as exc:
            if isinstance(exc, HttpRequestError):
                trace_id = exc.trace_id
            error = f"{type(exc).__name__}: {exc}"
        result = SurfaceResult(
            trial_id=trial_id,
            surface="generate",
            scenario_id=scenario.id,
            scenario_length=scenario.length,
            failure_modes=scenario.failure_modes,
            model=model,
            repetition=repetition,
            trace_id=trace_id,
            duration_seconds=time.monotonic() - started,
            response=response,
            checks=checks,
            usage=usage,
            error=error,
        )
        _write_surface_artifacts(
            output_dir=output_dir,
            result=result,
            request={
                "prompt": workspace.prompt,
                "include_other_code": workspace.include_other_code,
                "context_plain_text": workspace.context_plain_text,
            },
            candidate=source,
            workspace_root=root,
        )
        return result


def run_inline_scenario(
    scenario: InlineScenario,
    *,
    model: str,
    repetition: int,
    output_dir: Path,
    timeout_seconds: float,
) -> SurfaceResult:
    started = time.monotonic()
    trial_id = f"{scenario.id}-inline-{model_key(model)}-r{repetition:03d}"
    with tempfile.TemporaryDirectory(
        prefix=f"marimo-eval-{scenario.id}-"
    ) as temp:
        root = Path(temp)
        notebook = root / "analysis.py"
        notebook.write_text(
            "import marimo\n\napp = marimo.App()\n",
            encoding="utf-8",
        )
        completion = ""
        candidate = ""
        checks: list[CheckResult] = []
        error: str | None = None
        trace_id = ""
        try:
            with MarimoServer(
                root=root,
                notebook=notebook,
                model=model,
                timeout_seconds=timeout_seconds,
                eval_run_id=output_dir.name,
                scenario_id=scenario.id,
                trial_id=trial_id,
                repetition=repetition,
                variant=_SURFACE_VARIANT,
                session_id=f"eval-{output_dir.name}-{trial_id}",
            ) as server:
                turn = server.inline(
                    prefix=scenario.prefix,
                    suffix=scenario.suffix,
                    language=scenario.language,
                )
                trace_id = turn.trace_id
                completion = _trim_inline_response(
                    turn.completion, scenario.prefix, scenario.suffix
                )
                candidate = scenario.prefix + completion + scenario.suffix
                checks.extend(
                    CheckResult(
                        f"completion_matches:{pattern}",
                        re.search(pattern, completion) is not None,
                        f"required completion pattern: {pattern!r}",
                    )
                    for pattern in scenario.required_completion_patterns
                )
                checks.extend(
                    CheckResult(
                        f"completion_excludes:{fragment}",
                        fragment not in completion,
                        f"forbidden completion fragment: {fragment!r}",
                    )
                    for fragment in scenario.forbidden_completion_fragments
                )
                if scenario.language == "python":
                    checks.extend(
                        _evaluate_python(
                            candidate,
                            scenario.expected_summary,
                            root=root,
                        )
                    )
        except Exception as exc:
            if isinstance(exc, HttpRequestError):
                trace_id = exc.trace_id
            error = f"{type(exc).__name__}: {exc}"
        result = SurfaceResult(
            trial_id=trial_id,
            surface="inline",
            scenario_id=scenario.id,
            scenario_length=scenario.length,
            failure_modes=scenario.failure_modes,
            model=model,
            repetition=repetition,
            trace_id=trace_id,
            duration_seconds=time.monotonic() - started,
            response=completion,
            checks=checks,
            error=error,
        )
        _write_surface_artifacts(
            output_dir=output_dir,
            result=result,
            request={
                "prefix": scenario.prefix,
                "suffix": scenario.suffix,
                "language": scenario.language,
            },
            candidate=candidate,
            workspace_root=root,
        )
        return result


def _write_surface_artifacts(
    *,
    output_dir: Path,
    result: SurfaceResult,
    request: dict[str, JSONValue],
    candidate: str,
    workspace_root: Path,
) -> None:
    trial_dir = (
        output_dir
        / "trials"
        / model_key(result.model)
        / result.scenario_id
        / f"repetition-{result.repetition:03d}"
    )
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "result.json").write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    (trial_dir / "request.json").write_text(
        json.dumps(request, indent=2), encoding="utf-8"
    )
    (trial_dir / "candidate.py").write_text(candidate, encoding="utf-8")
    server_log = workspace_root / "marimo-server.log"
    if server_log.exists():
        shutil.copy2(server_log, trial_dir / "marimo-server.log")


def create_surface_run_directory(
    base: Path,
    *,
    surface: Literal["generate", "inline"],
    models: tuple[str, ...],
    scenarios: tuple[GenerateScenario, ...] | tuple[InlineScenario, ...],
    repetitions: int,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = base / f"{timestamp}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True)
    definitions: list[str] = []
    for scenario in scenarios:
        definitions.append(repr(scenario))
        setup = getattr(scenario, "setup", None)
        if setup is not None:
            definitions.append(inspect.getsource(setup))
    scenario_hash = hashlib.sha256("\n".join(definitions).encode()).hexdigest()
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    manifest = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "surface": surface,
        "logfire_query": logfire_run_query(run_dir.name),
        "models": list(models),
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


def write_surface_summary(run_dir: Path, results: list[SurfaceResult]) -> None:
    def interval(successes: int, total: int) -> tuple[float, float]:
        z = 1.96
        rate = successes / total
        denominator = 1 + z**2 / total
        centre = (rate + z**2 / (2 * total)) / denominator
        margin = (
            z
            * math.sqrt(rate * (1 - rate) / total + z**2 / (4 * total**2))
            / denominator
        )
        return max(0.0, centre - margin), min(1.0, centre + margin)

    def aggregate(trials: list[SurfaceResult]) -> dict[str, JSONValue]:
        passed = sum(trial.passed for trial in trials)
        pass_ci = interval(passed, len(trials))
        usage = sum((trial.usage for trial in trials), start=_ZERO_USAGE)
        return {
            "trials": len(trials),
            "passed": passed,
            "pass_rate": passed / len(trials),
            "pass_rate_ci95_low": pass_ci[0],
            "pass_rate_ci95_high": pass_ci[1],
            "mean_duration_seconds": statistics.mean(
                trial.duration_seconds for trial in trials
            ),
            "duration_stddev_seconds": statistics.pstdev(
                trial.duration_seconds for trial in trials
            ),
            "mean_input_tokens": usage.input_tokens / len(trials),
            "mean_output_tokens": usage.output_tokens / len(trials),
            "mean_response_chars": statistics.mean(
                len(json.dumps(trial.response, default=str))
                for trial in trials
            ),
        }

    scenario_groups: dict[tuple[str, str], list[SurfaceResult]] = {}
    model_groups: dict[str, list[SurfaceResult]] = {}
    for result in results:
        scenario_groups.setdefault(
            (result.model, result.scenario_id), []
        ).append(result)
        model_groups.setdefault(result.model, []).append(result)
    summary = {
        "run_id": run_dir.name,
        "logfire_query": logfire_run_query(run_dir.name),
        "passed": all(result.passed for result in results),
        "scenario_aggregates": [
            {
                "model": model,
                "scenario_id": scenario_id,
                **aggregate(trials),
            }
            for (model, scenario_id), trials in sorted(scenario_groups.items())
        ],
        "model_aggregates": [
            {"model": model, **aggregate(trials)}
            for model, trials in sorted(model_groups.items())
        ],
        "cases": [result.to_dict() for result in results],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
