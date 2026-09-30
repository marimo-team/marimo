from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

from benchmarks.ai.models import (
    CheckResult,
    ExpectedValue,
    JSONValue,
    TokenUsage,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class GenerateWorkspace:
    notebook: Path
    prompt: str
    expected_summary: dict[str, ExpectedValue]
    prelude: str = ""
    include_other_code: str = ""
    context_plain_text: str = ""
    minimum_python_cells: int = 1
    maximum_python_cells: int | None = None
    required_source_patterns: tuple[str, ...] = ()
    forbidden_source_patterns: tuple[str, ...] = ()


class GenerateWorkspaceFactory(Protocol):
    def __call__(self, root: Path) -> GenerateWorkspace: ...


@dataclass(frozen=True)
class GenerateScenario:
    id: str
    description: str
    length: Literal["short", "medium", "long"]
    failure_modes: tuple[str, ...]
    setup: GenerateWorkspaceFactory


@dataclass(frozen=True)
class InlineScenario:
    id: str
    description: str
    length: Literal["short", "medium", "long"]
    failure_modes: tuple[str, ...]
    prefix: str
    suffix: str
    expected_summary: dict[str, ExpectedValue]
    language: Literal["python", "markdown", "sql"] = "python"
    required_completion_patterns: tuple[str, ...] = ()
    forbidden_completion_fragments: tuple[str, ...] = ()


@dataclass
class SurfaceResult:
    trial_id: str
    surface: Literal["generate", "inline"]
    scenario_id: str
    scenario_length: Literal["short", "medium", "long"]
    failure_modes: tuple[str, ...]
    model: str
    repetition: int
    trace_id: str
    duration_seconds: float
    response: JSONValue = None
    checks: list[CheckResult] = field(default_factory=list)
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
