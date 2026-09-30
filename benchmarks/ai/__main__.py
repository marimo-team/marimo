from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _load_repository_env() -> None:
    # This must happen before the first marimo import: tracing is initialized
    # at import time from MARIMO_TRACING and the standard OTEL variables.
    from dotenv import load_dotenv

    repository_root = Path(__file__).resolve().parents[2]
    env_file = repository_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)


def _list_models() -> int:
    api_key = os.environ.get("WANDB_API_KEY")
    if not api_key:
        sys.stderr.write("WANDB_API_KEY is not configured\n")
        return 2
    request = urllib.request.Request(
        "https://api.inference.wandb.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload: dict[str, Any] = json.load(response)
    except urllib.error.HTTPError as exc:
        sys.stderr.write(
            "W&B did not allow model catalog access "
            f"(HTTP {exc.code}). Pass a model ID directly to `run`.\n"
        )
        return 1
    for model in sorted(
        (item.get("id", "") for item in payload.get("data", [])),
        key=str.casefold,
    ):
        if model:
            sys.stdout.write(f"{model}\n")
    return 0


def _add_surface_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
) -> None:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        required=True,
        help="Model ID to run; repeat to compare multiple models",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        help="Scenario ID to run; repeat to select more than one",
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(".ai-eval-runs")
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--jobs", type=int, default=1)


def _run_surface(args: argparse.Namespace) -> int:
    from benchmarks.ai.surface_models import (
        GenerateScenario,
        InlineScenario,
        SurfaceResult,
    )
    from benchmarks.ai.surface_runner import (
        create_surface_run_directory,
        run_generate_scenario,
        run_inline_scenario,
        write_surface_summary,
    )
    from benchmarks.ai.surface_scenarios import (
        get_generate_scenarios,
        get_inline_scenarios,
    )

    if args.repeat < 1:
        raise ValueError("--repeat must be at least 1")
    if args.jobs < 1:
        raise ValueError("--jobs must be at least 1")
    selected = set(args.scenarios) if args.scenarios else None
    scenarios: tuple[GenerateScenario, ...] | tuple[InlineScenario, ...]
    if args.command == "generate":
        scenarios = get_generate_scenarios(selected)
    else:
        scenarios = get_inline_scenarios(selected)
    run_dir = create_surface_run_directory(
        args.output_dir,
        surface=args.command,
        models=tuple(args.models),
        scenarios=scenarios,
        repetitions=args.repeat,
    )
    trials = [
        (number, model, scenario, repetition)
        for number, (model, scenario, repetition) in enumerate(
            (
                (model, scenario, repetition)
                for model in args.models
                for scenario in scenarios
                for repetition in range(1, args.repeat + 1)
            ),
            start=1,
        )
    ]
    output_lock = threading.Lock()

    def execute(trial: tuple[int, str, Any, int]) -> tuple[int, SurfaceResult]:
        number, model, scenario, repetition = trial
        prefix = f"[{number}/{len(trials)}]"
        with output_lock:
            sys.stdout.write(
                f"{prefix} {model} / {scenario.id} / repetition {repetition}\n"
            )
            sys.stdout.flush()
        if args.command == "generate":
            result = run_generate_scenario(
                scenario,
                model=model,
                repetition=repetition,
                output_dir=run_dir,
                timeout_seconds=args.timeout,
            )
        else:
            result = run_inline_scenario(
                scenario,
                model=model,
                repetition=repetition,
                output_dir=run_dir,
                timeout_seconds=args.timeout,
            )
        with output_lock:
            status = "PASS" if result.passed else "FAIL"
            sys.stdout.write(
                f"{prefix} {status} {result.duration_seconds:.1f}s, "
                f"trace={result.trace_id or 'unavailable'}\n"
            )
            if result.error:
                sys.stdout.write(f"{prefix} {result.error}\n")
            sys.stdout.flush()
        return number, result

    numbered_results: list[tuple[int, SurfaceResult]] = []
    if args.jobs == 1:
        numbered_results = [execute(trial) for trial in trials]
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(args.jobs, len(trials)),
            thread_name_prefix=f"marimo-ai-{args.command}-eval",
        ) as executor:
            futures = [executor.submit(execute, trial) for trial in trials]
            for future in concurrent.futures.as_completed(futures):
                numbered_results.append(future.result())
    results = [
        result
        for _, result in sorted(numbered_results, key=lambda item: item[0])
    ]
    write_surface_summary(run_dir, results)
    sys.stdout.write(f"Results: {run_dir}\n")
    return 0 if all(result.passed for result in results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local benchmarks against marimo's editor AI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("models", help="List model IDs available from W&B")
    _add_surface_parser(
        subparsers,
        "generate",
        "Evaluate Generate with AI through /api/ai/completion",
    )
    _add_surface_parser(
        subparsers,
        "inline",
        "Evaluate inline completion through /api/ai/inline_completion",
    )

    run_parser = subparsers.add_parser("run", help="Run benchmark scenarios")
    run_parser.add_argument(
        "--model",
        action="append",
        dest="models",
        required=True,
        help="Model ID to run; repeat to compare multiple models",
    )
    run_parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        help="Scenario ID to run; repeat to select more than one",
    )
    run_parser.add_argument(
        "--suite",
        choices=(
            "quick",
            "full",
            "capabilities",
            "holdout",
            "regression",
            "all",
        ),
        default="quick",
        help="Scenario suite to use when --scenario is not provided",
    )
    run_parser.add_argument(
        "--variant",
        action="append",
        dest="variants",
        help="Harness variant ID; repeat to compare variants",
    )
    run_parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of trials for each scenario and variant",
    )
    run_parser.add_argument(
        "--output-dir", type=Path, default=Path(".ai-eval-runs")
    )
    run_parser.add_argument("--timeout", type=float, default=600.0)
    run_parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Maximum number of isolated trials to run concurrently",
    )
    args = parser.parse_args()

    _load_repository_env()
    if args.command == "models":
        return _list_models()
    if args.command in ("generate", "inline"):
        try:
            return _run_surface(args)
        except ValueError as exc:
            parser.error(str(exc))

    from benchmarks.ai.models import (
        HarnessVariant,
        Scenario,
        ScenarioResult,
        TurnMetrics,
    )
    from benchmarks.ai.runner import (
        create_run_directory,
        logfire_run_query,
        run_scenario,
        write_summary,
    )
    from benchmarks.ai.scenarios import get_scenarios
    from benchmarks.ai.variants import get_variants

    if args.repeat < 1:
        run_parser.error("--repeat must be at least 1")
    if args.jobs < 1:
        run_parser.error("--jobs must be at least 1")
    scenario_ids = set(args.scenarios) if args.scenarios else None
    scenarios = get_scenarios(scenario_ids, suite=args.suite)
    variants = get_variants(set(args.variants) if args.variants else None)
    run_dir = create_run_directory(
        args.output_dir, tuple(args.models), scenarios, variants, args.repeat
    )
    total_trials = (
        len(args.models) * len(scenarios) * len(variants) * args.repeat
    )
    trials = [
        (trial_number, model, scenario, variant, repetition)
        for trial_number, (model, scenario, variant, repetition) in enumerate(
            (
                (model, scenario, variant, repetition)
                for model in args.models
                for scenario in scenarios
                for variant in variants
                for repetition in range(1, args.repeat + 1)
            ),
            start=1,
        )
    ]
    output_lock = threading.Lock()

    def write_output(message: str) -> None:
        with output_lock:
            sys.stdout.write(message)
            sys.stdout.flush()

    def execute_trial(
        trial: tuple[int, str, Scenario, HarnessVariant, int],
    ) -> tuple[int, ScenarioResult]:
        trial_number, model, scenario, variant, repetition = trial
        prefix = f"[{trial_number}/{total_trials}]"
        write_output(
            f"{prefix} {model} / {scenario.id} / {variant.id} / "
            f"repetition {repetition}\n"
        )

        def report_turn(metrics: TurnMetrics, total_turns: int) -> None:
            turn_prefix = f"{prefix} " if args.jobs > 1 else "    "
            write_output(
                f"{turn_prefix}turn {metrics.turn_number}/{total_turns}: "
                f"{metrics.duration_seconds:.1f}s, "
                f"{metrics.tool_calls} tools, "
                f"{metrics.tool_errors} errors, "
                f"{metrics.usage.requests} model requests, "
                f"{metrics.usage.input_tokens} input tokens, "
                f"{metrics.usage.output_tokens} output tokens, "
                f"trace={metrics.trace_id or 'unavailable'}\n"
            )

        result = run_scenario(
            scenario,
            model=model,
            variant=variant,
            repetition=repetition,
            output_dir=run_dir,
            timeout_seconds=args.timeout,
            on_turn=report_turn,
        )
        status = "PASS" if result.passed else "FAIL"
        write_output(
            f"{prefix} {status} {result.duration_seconds:.1f}s, "
            f"{len(result.trace_ids)} turn trace(s)\n"
        )
        if result.error:
            write_output(f"{prefix} {result.error}\n")
        return trial_number, result

    numbered_results: list[tuple[int, ScenarioResult]] = []
    if args.jobs == 1:
        numbered_results = [execute_trial(trial) for trial in trials]
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(args.jobs, total_trials),
            thread_name_prefix="marimo-ai-eval",
        ) as executor:
            futures = [
                executor.submit(execute_trial, trial) for trial in trials
            ]
            for future in concurrent.futures.as_completed(futures):
                numbered_results.append(future.result())

    results = [
        result
        for _, result in sorted(numbered_results, key=lambda item: item[0])
    ]
    write_summary(run_dir, results)
    sys.stdout.write(f"Results: {run_dir}\n")
    sys.stdout.write(f"Logfire: {logfire_run_query(run_dir.name)}\n")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
