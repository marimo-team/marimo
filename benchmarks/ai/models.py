from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from pathlib import Path


JSONValue = (
    None
    | bool
    | int
    | float
    | str
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)


@dataclass(frozen=True)
class NumericExpectation:
    value: int | float
    absolute_tolerance: float = 1e-6


ExpectedValue = JSONValue | NumericExpectation


@dataclass(frozen=True)
class ScenarioWorkspace:
    notebook: Path
    expected_summary: dict[str, ExpectedValue]
    required_source_fragments: tuple[str, ...] = ()
    required_source_patterns: tuple[str, ...] = ()
    forbidden_source_fragments: tuple[str, ...] = ()
    required_source_order: tuple[tuple[str, str], ...] = ()
    required_exact_cell_sources: tuple[str, ...] = ()
    turn_attachments: dict[int, tuple[FileAttachment, ...]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class FileAttachment:
    path: Path
    media_type: str
    filename: str


@dataclass(frozen=True)
class LiveCellEdit:
    before_turn: int
    cell_name: str
    code: str


class WorkspaceFactory(Protocol):
    def __call__(self, root: Path) -> ScenarioWorkspace: ...


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    length: Literal["short", "medium", "long"]
    failure_modes: tuple[str, ...]
    turns: tuple[str, ...]
    setup: WorkspaceFactory
    isolated_environment: bool = False
    live_cell_edits: tuple[LiveCellEdit, ...] = ()
    requires_vision: bool = False


@dataclass(frozen=True)
class HarnessVariant:
    id: str
    description: str
    mode: Literal["code_mode"] = "code_mode"
    max_tokens: int | None = None
    custom_rules: str | None = None
    tool_strategy: Literal["code_mode", "hybrid_balanced"] = "code_mode"
    history_strategy: Literal[
        "none",
        "semantic",
        "incremental_checkpoint",
    ] = "none"
    checkpoint_threshold_chars: int | None = None


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class TokenUsage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            requests=self.requests + other.requests,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens
            + other.cache_write_tokens,
        )


@dataclass(frozen=True)
class ToolCallMetrics:
    name: str
    input_chars: int
    output_chars: int
    errored: bool


@dataclass(frozen=True)
class TurnMetrics:
    turn_number: int
    trace_id: str
    duration_seconds: float
    tool_calls: int
    tool_errors: int
    usage: TokenUsage
    response_chars: int
    request_history_chars: int = 0
    effective_history_chars: int = 0
    assistant_message_chars: int = 0
    checkpoint_generated: bool = False
    checkpoint_duration_seconds: float = 0.0
    checkpoint_input_chars: int = 0
    tool_metrics: tuple[ToolCallMetrics, ...] = ()


@dataclass
class ScenarioResult:
    trial_id: str
    scenario_id: str
    scenario_length: Literal["short", "medium", "long"]
    failure_modes: tuple[str, ...]
    variant_id: str
    repetition: int
    model: str
    conversation_id: str
    trace_ids: list[str]
    duration_seconds: float
    observed_summary: dict[str, JSONValue] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)
    assistant_responses: list[str] = field(default_factory=list)
    turn_metrics: list[TurnMetrics] = field(default_factory=list)
    turns_completed: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(
            check.passed for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["passed"] = self.passed
        return result
