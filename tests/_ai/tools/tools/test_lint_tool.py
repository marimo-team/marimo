from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.lint import LintNotebook, LintNotebookArgs
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._schemas.serialization import NotebookSerializationV1
from marimo._types.ids import SessionId


@dataclass
class MockInternalApp:
    def to_ir(self) -> NotebookSerializationV1:
        # Return a minimal notebook IR
        return Mock(spec=NotebookSerializationV1)


@dataclass
class MockAppFileManager:
    app: MockInternalApp


@dataclass
class MockSession:
    app_file_manager: MockAppFileManager


async def test_lint_notebook_no_issues() -> None:
    """Test linting a notebook with no issues."""
    tool = LintNotebook(ToolContext())

    # Mock session with app
    session = MockSession(
        app_file_manager=MockAppFileManager(app=MockInternalApp())
    )

    # Mock ToolContext.get_session
    context = Mock(spec=ToolContext)
    context.get_session.return_value = session
    tool.context = context  # type: ignore[assignment]

    # Mock RuleEngine to return no diagnostics
    from unittest.mock import patch

    with patch(
        "marimo._ai._tools.tools.lint.RuleEngine.create_default"
    ) as mock_create:
        mock_engine = Mock()
        mock_engine.check_notebook = AsyncMock(return_value=[])
        mock_create.return_value = mock_engine

        out = await tool.handle(LintNotebookArgs(session_id=SessionId("s1")))

    assert out.summary.total_issues == 0
    assert out.summary.breaking_issues == 0
    assert out.summary.runtime_issues == 0
    assert out.summary.formatting_issues == 0
    assert len(out.diagnostics) == 0
    assert out.next_steps is not None
    assert "No issues found" in out.next_steps[0]


async def test_lint_notebook_with_issues() -> None:
    """Test linting a notebook with various types of issues."""
    tool = LintNotebook(ToolContext())

    # Mock session with app
    session = MockSession(
        app_file_manager=MockAppFileManager(app=MockInternalApp())
    )

    # Mock ToolContext.get_session
    context = Mock(spec=ToolContext)
    context.get_session.return_value = session
    tool.context = context  # type: ignore[assignment]

    # Create mock diagnostics
    breaking_diagnostic = Diagnostic(
        message="Breaking error",
        line=1,
        column=0,
        code="MB001",
        name="breaking_rule",
        severity=Severity.BREAKING,
        fixable=False,
    )

    runtime_diagnostic = Diagnostic(
        message="Runtime warning",
        line=2,
        column=0,
        code="MR001",
        name="runtime_rule",
        severity=Severity.RUNTIME,
        fixable=True,
    )

    formatting_diagnostic = Diagnostic(
        message="Formatting issue",
        line=3,
        column=0,
        code="MF001",
        name="formatting_rule",
        severity=Severity.FORMATTING,
        fixable="unsafe",
    )

    # Mock RuleEngine to return diagnostics
    from unittest.mock import patch

    with patch(
        "marimo._ai._tools.tools.lint.RuleEngine.create_default"
    ) as mock_create:
        mock_engine = Mock()
        mock_engine.check_notebook = AsyncMock(
            return_value=[
                breaking_diagnostic,
                runtime_diagnostic,
                formatting_diagnostic,
            ]
        )
        mock_create.return_value = mock_engine

        out = await tool.handle(LintNotebookArgs(session_id=SessionId("s1")))

    # Check counts
    assert out.summary.total_issues == 3
    assert out.summary.breaking_issues == 1
    assert out.summary.runtime_issues == 1
    assert out.summary.formatting_issues == 1

    # Check diagnostics
    assert len(out.diagnostics) == 3
    assert out.diagnostics[0].message == "Breaking error"
    assert out.diagnostics[0].severity == Severity.BREAKING
    assert out.diagnostics[0].code == "MB001"
    assert out.diagnostics[0].fixable is False

    assert out.diagnostics[1].message == "Runtime warning"
    assert out.diagnostics[1].severity == Severity.RUNTIME
    assert out.diagnostics[1].fixable is True

    assert out.diagnostics[2].message == "Formatting issue"
    assert out.diagnostics[2].severity == Severity.FORMATTING
    assert out.diagnostics[2].fixable == "unsafe"

    # Check next steps
    assert out.next_steps is not None
    assert len(out.next_steps) == 3
    assert "breaking" in out.next_steps[0].lower()
    assert "runtime" in out.next_steps[1].lower()
    assert "formatting" in out.next_steps[2].lower()
