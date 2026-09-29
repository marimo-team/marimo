from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.ai.models import (
    HarnessVariant,
    NumericExpectation,
    ScenarioResult,
    ScenarioWorkspace,
    TokenUsage,
    ToolCallMetrics,
)
from benchmarks.ai.runner import (
    _compare_summary,
    _source_contract_checks,
    logfire_run_query,
    write_summary,
)
from benchmarks.ai.scenarios import get_scenarios
from benchmarks.ai.server import MarimoServer, parse_summary_response
from benchmarks.ai.variants import get_variants
from benchmarks.ai.vercel_stream import AssistantMessageBuilder, parse_sse


def test_reconstructs_ui_message_from_vercel_stream() -> None:
    body = """data: {"type":"start","messageId":"message-1"}

data: {"type":"start-step"}

data: {"type":"text-start","id":"text-1"}

data: {"type":"text-delta","id":"text-1","delta":"Done"}

data: {"type":"tool-input-available","toolCallId":"call-1","toolName":"execute_code","input":{"code":"1 + 1"}}

data: {"type":"tool-output-available","toolCallId":"call-1","output":{"success":true}}

data: {"type":"data-marimo-usage","data":{"requests":2,"input_tokens":12,"output_tokens":7,"reasoning_tokens":3,"cache_read_tokens":4,"cache_write_tokens":1},"transient":true}

data: {"type":"finish","finishReason":"stop"}"""
    builder = AssistantMessageBuilder()
    for chunk in parse_sse(body):
        builder.add(chunk)

    assert builder.build() == {
        "id": "message-1",
        "role": "assistant",
        "parts": [
            {"type": "step-start"},
            {"type": "text", "text": "Done"},
            {
                "type": "tool-execute_code",
                "toolCallId": "call-1",
                "state": "output-available",
                "input": {"code": "1 + 1"},
                "output": {"success": True},
            },
        ],
    }
    assert builder.tool_calls == 1
    assert builder.tool_errors == 0
    assert builder.tool_metrics == (
        ToolCallMetrics(
            name="execute_code",
            input_chars=len('{"code":"1 + 1"}'),
            output_chars=len('{"success":true}'),
            errored=False,
        ),
    )
    assert builder.usage == TokenUsage(
        requests=2,
        input_tokens=12,
        output_tokens=7,
        reasoning_tokens=3,
        cache_read_tokens=4,
        cache_write_tokens=1,
    )
    assert builder.finish_reason == "stop"


def test_reads_legacy_usage_from_finish_chunk() -> None:
    builder = AssistantMessageBuilder()
    builder.add(
        {
            "type": "finish",
            "finishReason": "stop",
            "usage": {"inputTokens": 12, "outputTokens": 7},
        }
    )

    assert builder.usage == TokenUsage(input_tokens=12, output_tokens=7)


def test_compare_summary_supports_numeric_tolerance() -> None:
    checks = _compare_summary(
        {"revenue": 10.0000001, "segment": "enterprise"},
        {"revenue": 10.0, "segment": "Enterprise"},
    )

    assert all(check.passed for check in checks)


def test_compare_summary_supports_metric_specific_tolerance() -> None:
    checks = _compare_summary(
        {"percent_change": -38.596491228},
        {"percent_change": NumericExpectation(-38.6, 0.05)},
    )

    assert checks[0].passed


def test_parse_summary_response_accumulates_fragmented_stdout() -> None:
    body = """event: stdout
data: {"data":"__MARIMO_AI_EVAL__"}

event: stdout
data: {"data":"{\\"revenue\\":"}

event: stdout
data: {"data":" 42}\\n"}
"""

    assert parse_summary_response(body) == {"revenue": 42}


def test_parse_summary_response_does_not_parse_stderr_source() -> None:
    body = """event: stderr
data: {"data":"NameError in print('__MARIMO_AI_EVAL__' + value)"}

event: done
data: {"success":false}
"""

    with pytest.raises(RuntimeError, match="NameError"):
        parse_summary_response(body)


def test_logfire_run_query_selects_eval_run_attribute() -> None:
    assert logfire_run_query("run-123") == (
        "attributes->>'marimo.ai.eval.run_id' = 'run-123'"
    )


def test_retail_fixture_contains_known_join_trap(tmp_path: Path) -> None:
    scenario = get_scenarios({"retail_investigation_short"})[0]
    workspace = scenario.setup(tmp_path)

    customers = (tmp_path / "data" / "customers.csv").read_text()
    assert customers.count("c2,SMB,North,false") == 2
    assert workspace.expected_summary["q1_net_revenue"] == 2850.0
    assert workspace.expected_summary["q2_net_revenue"] == 1750.0


def test_scenario_selection_reports_unknown_ids() -> None:
    with pytest.raises(ValueError, match="Unknown scenario") as exc_info:
        get_scenarios({"missing"})

    assert str(exc_info.value) == "Unknown scenario(s): missing"


def test_scenario_suite_has_intentional_length_distribution() -> None:
    scenarios = get_scenarios()

    assert len(scenarios) == 10
    assert sum(scenario.length == "short" for scenario in scenarios) == 3
    assert sum(scenario.length == "medium" for scenario in scenarios) == 4
    assert sum(scenario.length == "long" for scenario in scenarios) == 3
    assert all(scenario.failure_modes for scenario in scenarios)
    assert len({scenario.id for scenario in scenarios}) == len(scenarios)


def test_quick_suite_avoids_long_scenarios() -> None:
    scenarios = get_scenarios(suite="quick")

    assert {scenario.id for scenario in scenarios} == {
        "athletes_prescribed",
        "retail_investigation_short",
    }


def test_capability_suite_covers_distinct_editor_operations() -> None:
    scenarios = get_scenarios(suite="capabilities")

    assert {scenario.id for scenario in scenarios} == {
        "package_lifecycle",
        "ui_state_interaction",
        "cell_layout_configuration",
    }
    package_scenario = next(
        scenario
        for scenario in scenarios
        if scenario.id == "package_lifecycle"
    )
    assert package_scenario.isolated_environment is True


def test_package_scenario_builds_local_wheels(tmp_path: Path) -> None:
    scenario = get_scenarios({"package_lifecycle"})[0]

    workspace = scenario.setup(tmp_path)

    assert workspace.notebook.exists()
    assert sorted(path.name for path in (tmp_path / "packages").iterdir()) == [
        "eval_robust-0.1.0-py3-none-any.whl",
        "eval_transformer-0.1.0-py3-none-any.whl",
    ]


def test_source_contract_checks_content_and_order(tmp_path: Path) -> None:
    workspace = ScenarioWorkspace(
        notebook=tmp_path / "analysis.py",
        expected_summary={},
        required_source_fragments=("hide_code=True",),
        forbidden_source_fragments=("old_package",),
        required_source_order=(("def summary", "def chart"),),
    )

    checks = _source_contract_checks(
        "@app.cell(hide_code=True)\ndef summary(): ...\ndef chart(): ...",
        workspace,
    )

    assert all(check.passed for check in checks)


def test_variant_selection_defaults_to_baseline() -> None:
    assert [variant.id for variant in get_variants()] == ["baseline"]
    assert [variant.id for variant in get_variants({"hybrid_balanced"})] == [
        "hybrid_balanced"
    ]


def test_summary_aggregates_repeated_trials(tmp_path: Path) -> None:
    results = [
        ScenarioResult(
            trial_id=f"case-baseline-r{repetition:03d}",
            scenario_id="case",
            scenario_length="short",
            failure_modes=("test",),
            variant_id="baseline",
            repetition=repetition,
            model="provider/model",
            conversation_id=f"conversation-{repetition}",
            trace_ids=[],
            duration_seconds=duration,
            tool_calls=tool_calls,
            usage=TokenUsage(
                requests=repetition,
                input_tokens=100 * repetition,
                output_tokens=10 * repetition,
            ),
        )
        for repetition, duration, tool_calls in (
            (1, 10.0, 2),
            (2, 14.0, 4),
        )
    ]

    write_summary(tmp_path, results)

    summary = json.loads((tmp_path / "summary.json").read_text())
    aggregate = summary["scenario_aggregates"][0]
    assert aggregate["trials"] == 2
    assert aggregate["pass_rate"] == 1.0
    assert aggregate["mean_duration_seconds"] == 12.0
    assert aggregate["duration_stddev_seconds"] == 2.0
    assert aggregate["mean_tool_calls"] == 3
    assert aggregate["total_model_requests"] == 3
    assert aggregate["mean_input_tokens"] == 150
    assert aggregate["total_output_tokens"] == 30
    assert aggregate["total_request_history_chars"] == 0
    assert aggregate["total_effective_history_chars"] == 0
    assert aggregate["total_tool_output_chars"] == 0
    assert aggregate["tool_payloads"] == {}
    assert summary["variant_aggregates"][0]["pass_rate"] == 1.0
    assert summary["length_aggregates"][0]["scenario_length"] == "short"


def test_server_config_isolates_user_preferences(tmp_path: Path) -> None:
    notebook = tmp_path / "analysis.py"
    server = MarimoServer(
        root=tmp_path,
        notebook=notebook,
        model="provider/model",
        timeout_seconds=1,
        eval_run_id="run-123",
        scenario_id="scenario-123",
        trial_id="scenario-123-baseline-r001",
        repetition=1,
        variant=HarnessVariant(
            id="validation_first",
            description="Test variant",
            custom_rules="Inspect before editing.",
        ),
    )

    server._write_config()

    assert (tmp_path / ".marimo.toml").read_text() == ""
    config = (tmp_path / "pyproject.toml").read_text()
    assert 'chat_model = "wandb/provider/model"' in config
    assert 'api_key = "env:WANDB_API_KEY"' in config
    assert 'rules = "Inspect before editing."' in config
    assert "max_tokens" not in config


@pytest.mark.requires("pydantic_ai")
def test_server_environment_isolates_package_changes(tmp_path: Path) -> None:
    server = MarimoServer(
        root=tmp_path,
        notebook=tmp_path / "analysis.py",
        model="provider/model",
        timeout_seconds=1,
        eval_run_id="run-123",
        scenario_id="scenario-123",
        trial_id="scenario-123-baseline-r001",
        repetition=1,
        variant=HarnessVariant(id="baseline", description="Baseline"),
        isolated_environment=True,
    )

    python, environment = server._server_environment()
    process = subprocess.run(
        [python, "-c", "import marimo; import pydantic_ai"],
        capture_output=True,
        env=environment,
        text=True,
        timeout=30,
    )

    assert process.returncode == 0, process.stderr
    assert python != Path(sys.executable)
    assert environment["VIRTUAL_ENV"] == str(tmp_path / ".benchmark-venv")
