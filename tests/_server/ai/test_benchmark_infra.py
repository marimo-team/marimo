from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.ai.models import (
    FileAttachment,
    HarnessVariant,
    NumericExpectation,
    ScenarioResult,
    ScenarioWorkspace,
    TokenUsage,
    ToolCallMetrics,
)
from benchmarks.ai.runner import (
    _compare_summary,
    _message,
    _source_contract_checks,
    create_run_directory,
    logfire_run_query,
    model_key,
    write_summary,
)
from benchmarks.ai.scenarios import get_scenarios
from benchmarks.ai.server import (
    HttpRequestError,
    MarimoServer,
    parse_summary_response,
)
from benchmarks.ai.surface_runner import (
    _evaluate_python,
    _generate_checks,
    _trim_inline_response,
    create_surface_run_directory,
)
from benchmarks.ai.surface_scenarios import (
    get_generate_scenarios,
    get_inline_scenarios,
)
from benchmarks.ai.variants import get_variants
from benchmarks.ai.vercel_stream import (
    AssistantMessageBuilder,
    StructuredCompletionBuilder,
    parse_sse,
)


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


def test_reads_structured_completion_and_usage() -> None:
    builder = StructuredCompletionBuilder(
        data_type="data-notebook-cells-completion"
    )
    for chunk in parse_sse(
        """data: {"type":"data-notebook-cells-completion","data":{"cells":[{"language":"python","code":"x = 1"}]}}

data: {"type":"data-marimo-usage","data":{"requests":1,"input_tokens":20,"output_tokens":5}}

data: {"type":"finish","finishReason":"stop"}
"""
    ):
        builder.add(chunk)

    assert builder.result() == {
        "cells": [{"language": "python", "code": "x = 1"}]
    }
    assert builder.usage == TokenUsage(
        requests=1, input_tokens=20, output_tokens=5
    )


def test_structured_completion_requires_successful_finish() -> None:
    builder = StructuredCompletionBuilder(data_type="data-cell-completion")
    builder.add({"type": "data-cell-completion", "data": {"code": "x = 1"}})

    with pytest.raises(RuntimeError, match="final validation"):
        builder.result()


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


def test_http_request_error_retains_diagnostics() -> None:
    error = HttpRequestError(500, '{"detail":"token limit"}', "trace-123")

    assert error.status_code == 500
    assert error.body == '{"detail":"token limit"}'
    assert error.trace_id == "trace-123"
    assert str(error) == 'HTTP 500: {"detail":"token limit"}'


def test_logfire_run_query_selects_eval_run_attribute() -> None:
    assert logfire_run_query("run-123") == (
        "attributes->>'marimo.ai.eval.run_id' = 'run-123'"
    )


def test_model_key_is_readable_and_collision_resistant() -> None:
    first = model_key("provider/model")
    second = model_key("provider:model")

    assert first.startswith("provider-model-")
    assert second.startswith("provider-model-")
    assert first != second


def test_retail_fixture_contains_known_join_trap(tmp_path: Path) -> None:
    scenario = get_scenarios({"retail_investigation_short"})[0]
    workspace = scenario.setup(tmp_path)

    customers = (tmp_path / "data" / "customers.csv").read_text()
    assert customers.count("c2,SMB,North,false") == 2
    assert workspace.expected_summary["q1_net_revenue"] == 2850.0
    assert workspace.expected_summary["q2_net_revenue"] == 1750.0


def test_orders_scenario_names_its_input_files() -> None:
    scenario = get_scenarios({"orders_missing_dimensions"})[0]

    assert "data/products.csv" in scenario.turns[0]
    assert "data/orders.csv" in scenario.turns[0]


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


def test_generate_and_inline_suites_cover_each_request_length() -> None:
    generate = get_generate_scenarios()
    inline = get_inline_scenarios()

    assert {scenario.length for scenario in generate} == {
        "short",
        "medium",
        "long",
    }
    assert {scenario.length for scenario in inline} == {
        "short",
        "medium",
        "long",
    }
    assert all(scenario.failure_modes for scenario in (*generate, *inline))


def test_surface_scenario_selection_reports_unknown_ids() -> None:
    with pytest.raises(ValueError, match="Unknown generate scenario"):
        get_generate_scenarios({"missing"})
    with pytest.raises(ValueError, match="Unknown inline scenario"):
        get_inline_scenarios({"missing"})


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


def test_holdout_suite_covers_unseen_generalization_risks() -> None:
    scenarios = get_scenarios(suite="holdout")

    assert {scenario.id for scenario in scenarios} == {
        "historical_exact_restore",
        "large_reactive_graph_repair",
        "mixed_editor_capabilities",
        "campaign_clarification_long",
        "live_human_edit",
        "static_visual_review",
    }
    assert sum(scenario.length == "long" for scenario in scenarios) == 2
    visual = next(
        scenario
        for scenario in scenarios
        if scenario.id == "static_visual_review"
    )
    assert visual.requires_vision is True
    live_edit = next(
        scenario for scenario in scenarios if scenario.id == "live_human_edit"
    )
    assert live_edit.live_cell_edits[0].before_turn == 2
    failure_modes = {
        mode for scenario in scenarios for mode in scenario.failure_modes
    }
    assert len(failure_modes) >= 10


def test_regression_suite_covers_revision_restoration(tmp_path: Path) -> None:
    scenarios = get_scenarios(suite="regression")
    assert {scenario.id for scenario in scenarios} == {
        "rendered_output_review",
        "revision_history_restore",
    }
    scenario = next(
        scenario
        for scenario in scenarios
        if scenario.id == "revision_history_restore"
    )

    assert scenario.id == "revision_history_restore"
    assert {
        "multiple_cell_revisions",
        "deleted_cell_restoration",
        "exact_source_restoration",
    }.issubset(scenario.failure_modes)

    workspace = scenario.setup(tmp_path)
    source = workspace.notebook.read_text()
    checks = _source_contract_checks(source, workspace)
    exact_checks = [
        check
        for check in checks
        if check.name.startswith("exact_cell_source:")
    ]
    assert len(exact_checks) == 2
    assert all(check.passed for check in exact_checks)
    assert all(
        check.reason == "exact cell source matched" for check in exact_checks
    )


def test_rendered_output_review_fixture_has_visual_only_contract(
    tmp_path: Path,
) -> None:
    [scenario] = get_scenarios({"rendered_output_review"})
    workspace = scenario.setup(tmp_path)

    assert scenario.requires_vision is True
    assert workspace.turn_attachments == {}
    assert (tmp_path / "fixtures" / "rendered-output-review.png").exists()
    source = workspace.notebook.read_text()
    assert "MANGO-47" not in source
    assert "Quarterly Revenue" not in source
    checks = _source_contract_checks(source, workspace)
    assert any(not check.passed for check in checks)


def test_holdout_fixtures_have_expected_contracts(tmp_path: Path) -> None:
    (tmp_path / "graph").mkdir()
    (tmp_path / "mixed").mkdir()
    graph = get_scenarios({"large_reactive_graph_repair"})[0].setup(
        tmp_path / "graph"
    )
    mixed = get_scenarios({"mixed_editor_capabilities"})[0].setup(
        tmp_path / "mixed"
    )

    assert graph.expected_summary["final_value"] == 310
    assert "stage_13 = stage_12 + 90" in graph.notebook.read_text()
    assert mixed.expected_summary["scaled_total"] == 80.0
    wheel = (
        tmp_path / "mixed" / "packages" / "eval_scaler-0.1.0-py3-none-any.whl"
    )
    assert wheel.exists()


def test_visual_fixture_is_attached_as_a_ui_file_part(tmp_path: Path) -> None:
    (tmp_path / "visual").mkdir()
    workspace = get_scenarios({"static_visual_review"})[0].setup(
        tmp_path / "visual"
    )

    attachment = workspace.turn_attachments[1][0]
    message = _message("user", "Review this", (attachment,))

    assert message["parts"][0] == {"type": "text", "text": "Review this"}
    file_part = message["parts"][1]
    assert file_part["type"] == "file"
    assert file_part["mediaType"] == "image/png"
    assert file_part["filename"] == "visual-review.png"
    assert file_part["url"].startswith("data:image/png;base64,iVBOR")

    pandas_sort = _source_contract_checks(
        """def cell():
    chart = alt.Chart(revenue.sort_values("revenue", ascending=False))
    chart.encode(x=alt.X("product:N", axis=alt.Axis(labelAngle=-35)))
    chart.properties(width=650)
    chart
    return
""",
        workspace,
    )
    assert all(check.passed for check in pandas_sort)


def test_message_supports_direct_fixture_attachment(tmp_path: Path) -> None:
    path = tmp_path / "tiny.png"
    path.write_bytes(b"png")

    message = _message(
        "user",
        "image",
        (FileAttachment(path, "image/png", "tiny.png"),),
    )

    assert message["parts"][1]["url"] == "data:image/png;base64,cG5n"


def test_live_edit_uses_editor_run_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = MarimoServer(
        root=tmp_path,
        notebook=tmp_path / "analysis.py",
        model="provider/model",
        timeout_seconds=1,
        eval_run_id="run",
        scenario_id="scenario",
        trial_id="trial",
        repetition=1,
        variant=HarnessVariant(id="baseline", description="baseline"),
    )
    server._cell_ids_by_name = {"policy": "cell-policy"}
    calls: list[tuple[str, dict[str, object]]] = []
    statuses = iter(("running", "idle"))

    def record_post(
        path: str,
        body: dict[str, object],
        **_: object,
    ) -> object:
        calls.append((path, body))
        return object()

    monkeypatch.setattr(server, "_post", record_post)
    monkeypatch.setattr(server, "_kernel_status", lambda: next(statuses))

    server.edit_cell("policy", "value = 2")

    assert calls == [
        (
            "/api/kernel/run",
            {"cellIds": ["cell-policy"], "codes": ["value = 2"]},
        )
    ]


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
        required_source_patterns=(r"old|legacy",),
        forbidden_source_fragments=("old_package",),
        required_source_order=(("def summary", "def chart"),),
        required_exact_cell_sources=("value = 1",),
    )

    checks = _source_contract_checks(
        """import marimo

app = marimo.App()

@app.cell(hide_code=True)
def summary():
    value = 1
    return value

@app.cell
def chart(value):
    # legacy
    return value
""",
        workspace,
    )

    assert all(check.passed for check in checks)


def test_source_contract_checks_exact_cell_source(tmp_path: Path) -> None:
    source = """import marimo

app = marimo.App()

@app.cell
def _():
    value = 2
    return value
"""
    workspace = ScenarioWorkspace(
        notebook=tmp_path / "analysis.py",
        expected_summary={},
        required_exact_cell_sources=("value = 1",),
    )

    [check] = _source_contract_checks(source, workspace)

    assert check.name.startswith("exact_cell_source:")
    assert not check.passed


def test_inline_cleanup_matches_editor_behavior() -> None:
    assert (
        _trim_inline_response("prefixmiddle suffix", "prefix", " suffix")
        == "middle"
    )


def test_surface_python_evaluator_checks_behavior(tmp_path: Path) -> None:
    checks = _evaluate_python(
        'value = 6 * 7\nanalysis_summary = {"value": value}',
        {"value": 42},
        root=tmp_path,
    )

    assert all(check.passed for check in checks)


def test_generate_grader_checks_cells_source_and_behavior(
    tmp_path: Path,
) -> None:
    workspace = get_generate_scenarios({"generate_existing_context"})[0].setup(
        tmp_path
    )
    cells = (
        {
            "language": "python",
            "code": 'paid = [order for order in orders if order["status"] == "paid"]',
        },
        {
            "language": "python",
            "code": (
                "analysis_summary = {\n"
                '    "paid_count": len(paid),\n'
                '    "net_after_fees": sum(order["amount"] for order in paid) * (1 - fee_rate),\n'
                "}"
            ),
        },
    )

    checks, _ = _generate_checks(cells, workspace, root=tmp_path)

    assert all(check.passed for check in checks)


def test_surface_manifest_records_multiple_models(tmp_path: Path) -> None:
    scenarios = get_inline_scenarios({"inline_filter_expression"})
    run_dir = create_surface_run_directory(
        tmp_path,
        surface="inline",
        models=("provider/one", "provider/two"),
        scenarios=scenarios,
        repetitions=3,
    )

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["models"] == ["provider/one", "provider/two"]
    assert manifest["repetitions"] == 3
    assert manifest["surface"] == "inline"


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
    assert aggregate["model"] == "provider/model"
    assert aggregate["pass_rate"] == 1.0
    assert 0 < aggregate["pass_rate_ci95_low"] < 1
    assert aggregate["pass_rate_ci95_high"] == 1.0
    assert aggregate["mean_duration_seconds"] == 12.0
    assert aggregate["duration_stddev_seconds"] == 2.0
    assert aggregate["mean_duration_ci95_low"] < 12.0
    assert aggregate["mean_duration_ci95_high"] > 12.0
    assert aggregate["mean_tool_calls"] == 3
    assert aggregate["total_model_requests"] == 3
    assert aggregate["mean_input_tokens"] == 150
    assert aggregate["input_tokens_stddev"] == 50
    assert aggregate["total_output_tokens"] == 30
    assert aggregate["total_request_history_chars"] == 0
    assert aggregate["total_effective_history_chars"] == 0
    assert aggregate["total_tool_output_chars"] == 0
    assert aggregate["tool_payloads"] == {}
    assert summary["variant_aggregates"][0]["pass_rate"] == 1.0
    assert summary["model_aggregates"][0]["model"] == "provider/model"
    assert summary["length_aggregates"][0]["scenario_length"] == "short"


def test_chat_manifest_records_multiple_models(tmp_path: Path) -> None:
    run_dir = create_run_directory(
        tmp_path,
        ("provider/one", "provider/two"),
        get_scenarios(suite="quick"),
        get_variants({"baseline"}),
        2,
    )

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["schema_version"] == 7
    assert manifest["models"] == ["provider/one", "provider/two"]
    assert manifest["repetitions"] == 2


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
    assert 'edit_model = "wandb/provider/model"' in config
    assert 'autocomplete_model = "wandb/provider/model"' in config
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
