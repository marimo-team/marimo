
# Adding Backend and MCP Tools to marimo

This guide explains how to create tools that are accessible via both the backend (chat panel) and MCP (Model Context Protocol) server endpoints.

## Overview

marimo provides a unified framework for creating tools that can be used by AI assistants to interact with notebooks. These tools are automatically registered in both:

1. **Backend Tools**: Used by the marimo chat panel (ask/agent modes)
2. **MCP Tools**: Exposed via the MCP server endpoint for external AI clients (like Claude Desktop)

The unified architecture means you write a tool once and it works in both contexts.

## Step-by-Step Implementation

### 1. Create the Tool File

Create a new file in `marimo/_ai/_tools/tools/your_tool.py` for your tool implementation.

### 2. Define Input and Output Types

Create dataclasses for your tool's arguments and output. Place these at the top of your tool file.

**Template:**

---
```python
from dataclasses import dataclass, field
from marimo._ai._tools.types import SuccessResult
from marimo._types.ids import SessionId


@dataclass
class YourToolArgs:
    """Arguments for your tool."""
    session_id: SessionId
    # Add other required parameters
    optional_param: str = "default_value"


@dataclass
class YourToolOutput(SuccessResult):
    """Output from your tool."""
    # Add your output fields
    data: dict = field(default_factory=dict)
    count: int = 0
```
---

**Important Type Patterns:**

- **Naming Convention**: Input dataclasses must end with `Args`, output dataclasses must end with `Output`
- Input args should use plain dataclasses
- Output should inherit from `SuccessResult` (provides `status`, `next_steps`, `message`, etc.)
- Use `field(default_factory=...)` for mutable defaults (lists, dicts)
- Use marimo types like `SessionId`, `CellId_t` for consistency

### 3. Create the Tool Class

Implement your tool class in the same file:

**Template:**

---
```python
# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import SuccessResult, ToolGuidelines
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._types.ids import SessionId

if TYPE_CHECKING:
    from marimo._server.sessions import Session


@dataclass
class YourToolArgs:
    """Arguments for your tool."""
    session_id: SessionId
    # Add parameters here


@dataclass
class YourToolOutput(SuccessResult):
    """Output from your tool."""
    # Add output fields here
    sample_dict: dict = field(default_factory=dict)


class YourTool(ToolBase[YourToolArgs, YourToolOutput]):
    """Brief description of what this tool does.

    More detailed explanation of the tool's purpose and functionality.
    This docstring becomes the tool's description shown to AI assistants.

    Args:
        session_id: The session ID of the notebook
        # Document other args

    Returns:
        A success result containing [describe what it returns].
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "When [describe primary use case]",
        ],
        prerequisites=[
            "You must [describe args that need additional explanation]",
        ],
        avoid_if=[
            "When [describe when not to use]",
        ],
        additional_info=(
            "Any additional context or warnings about tool usage."
        ),
    )

    def handle(self, args: YourToolArgs) -> YourToolOutput:
        """Implement your tool logic here."""
        # ToolContext provides access to sessions, notebooks, and all marimo state
        context = self.context
        session_id = args.session_id
        session = context.get_session(session_id)

        # Implement your logic
        sample_dict = self._do_work(session)

        return YourToolOutput(
            sample_dict=sample_dict,
            next_steps=[
                "Review the results",
                "Consider next actions",
            ],
            message="Optionally add this is the results require more explanation",
        )

    # Helper methods (prefix with _)
    def _do_work(self, session: Session) -> dict:
        """Private helper method."""
        # Implementation details
        return {}
```
---

### 4. Understanding ToolContext

`ToolContext` is your gateway to all marimo state—sessions, notebooks, cells, errors, and more. It's available via `self.context` in your tool.

#### How to access ToolContext in your tool

Access via `self.context` in your `handle()` method:

---
```python
def handle(self, args: YourToolArgs) -> YourToolOutput:
    # Access ToolContext
    context = self.context

    # Use context methods
    session = context.get_session(args.session_id)
    errors = context.get_notebook_errors(args.session_id)
```
---

#### When to add to ToolContext vs a helper method

**Add to ToolContext when:**
- The functionality will be used by **multiple tools**
- It accesses core marimo state (sessions, cells, errors)
- It provides a common pattern that should be consistent across tools

**Use helper methods when:**
- The logic is specific to **your tool only**
- It's a one-off data transformation or validation
- It doesn't need to access marimo state beyond what you already have

**Example:**

---
```python
class YourTool(ToolBase[YourToolArgs, YourToolOutput]):
    def handle(self, args: YourToolArgs) -> YourToolOutput:
        # Use ToolContext for common operations
        session = self.context.get_session(args.session_id)
        errors = self.context.get_notebook_errors(args.session_id)

        # Use helper methods for tool-specific logic
        filtered_data = self._filter_by_criteria(errors, args.criteria)

        return YourToolOutput(data=filtered_data)

    def _filter_by_criteria(self, errors: list, criteria: str) -> list:
        """Tool-specific logic as a helper method."""
        return [e for e in errors if criteria in e.message]
```
---

#### Available ToolContext Methods

For the current and complete list of available methods, see `marimo/_ai/_tools/base.py` in the `ToolContext` class. Common methods include:
- `get_session(session_id)` - Get a notebook session
- `get_notebook_errors(session_id, include_stderr)` - Get all errors in a notebook
- `get_cell_errors(session_id, cell_id)` - Get errors for a specific cell
- `get_active_sessions_internal()` - Get list of active notebook sessions

### 5. Understanding ToolGuidelines

`ToolGuidelines` help AI assistants understand when and how to use your tool. Customize based on your tool's specific use case.

**Fields:**

- **`when_to_use`**: List specific scenarios where your tool is appropriate
  - Example: `"When the user needs to inspect cell outputs"`

- **`avoid_if`**: List scenarios where your tool should NOT be used
  - Example: `"When the session hasn't been started yet"`

- **`prerequisites`**: Required state or information before using the tool
  - Example: `"Valid session ID from an active notebook"` (only if accessing notebook data)

- **`side_effects`**: Any state changes your tool makes
  - Example: `"Modifies notebook cells"`, `"Triggers cell re-execution"`

- **`additional_info`**: Additional context or warnings (single string)
  - Example: `"This tool provides static analysis only"`

**⚠️ Warning:** Too many guidelines can confuse the AI agent. Less is more—only add guidelines when you clearly understand the use cases. If you're unsure, keep it minimal

### 6. Error Handling

#### When to Use Try/Except

**Only use try/except when you need to catch a specific error and provide tailored guidance to the AI agent.**

- ✅ **Use try/except**: For expected errors where you want to guide the agent (e.g., "Use get_lightweight_cell_map to find valid cell IDs")
- ❌ **Don't use try/except**: For unexpected errors—they're automatically wrapped in `ToolExecutionError` and surfaced to the agent

#### Using ToolExecutionError

Use `ToolExecutionError` for expected failures:

---
```python
from marimo._ai._tools.utils.exceptions import ToolExecutionError

# Raise structured errors
raise ToolExecutionError(
    "Clear description of what went wrong",
    code="ERROR_CODE",  # Machine-readable code
    is_retryable=True,  # Can the user retry?
    suggested_fix="How to fix the issue",  # User-friendly guidance
    meta={"session_id": session_id},  # Additional context
)
```
---

**Common Error Codes:**

- `SESSION_NOT_FOUND`: Session ID doesn't exist
- `CELL_NOT_FOUND`: Cell ID doesn't exist
- `BAD_ARGUMENTS`: Invalid arguments passed
- `OPERATION_FAILED`: Generic operation failure
- `UNEXPECTED_ERROR`: Uncaught exception (handled automatically)

**Error Handling Best Practices:**

---
```python
def handle(self, args: YourToolArgs) -> YourToolOutput:
    # ToolContext methods automatically raise ToolExecutionError if session not found
    session = self.context.get_session(args.session_id)

    # Validate inputs - raise ToolExecutionError directly for validation errors
    if args.count < 0:
        raise ToolExecutionError(
            "Count must be non-negative",
            code="INVALID_COUNT",
            is_retryable=False,
            suggested_fix="Provide a count >= 0",
        )

    # Only use try/except for specific expected errors where you want to guide the agent
    try:
        result = self._operation_that_might_fail()
    except ValueError as e:
        # Caught specific error - provide tailored guidance
        raise ToolExecutionError(
            f"Invalid cell ID: {e}",
            code="INVALID_CELL_ID",
            is_retryable=False,
            suggested_fix="Use get_lightweight_cell_map to find valid cell IDs",
        )

    # Don't wrap everything in try/except - unexpected errors are handled automatically
    return YourToolOutput(data=result)
```
---

### 7. Register the Tool

Add your tool to the registry in `marimo/_ai/_tools/tools_registry.py`:

---
```python
from marimo._ai._tools.tools.your_tool import YourTool

SUPPORTED_BACKEND_AND_MCP_TOOLS: list[type[ToolBase[Any, Any]]] = [
    GetMarimoRules,
    GetActiveNotebooks,
    # ... existing tools ...
    YourTool,  # Add your tool here
]
```
---

**That's it!** Your tool is now automatically registered in both backend and MCP contexts.

### 8. Add Args and Output to msgspec tests

Add your tool's Args and Output classes to the `TOOL_IO_CLASSES` list in `tests/_utils/test_msgspec_basestruct.py`. This ensures type compatibility between our serialization system and pydantic (used by the python mcp sdk).

---
```python
from marimo._ai._tools.tools.your_tool import (
    YourToolArgs,
    YourToolOutput,
)

TOOL_IO_CLASSES = [
    # ... existing classes ...
    YourToolArgs,
    YourToolOutput,
]
```
---

### 9. Create Tests

#### Unit Tests

Create `tests/_ai/tools/tools/test_your_tool.py`:

---
```python
from __future__ import annotations

from unittest.mock import Mock

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.your_tool import (
    YourTool,
    YourToolArgs,
)
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._types.ids import SessionId


@pytest.fixture
def tool() -> YourTool:
    """Create a YourTool instance."""
    return YourTool(ToolContext())


@pytest.fixture
def mock_context() -> Mock:
    """Create a mock ToolContext."""
    return Mock(spec=ToolContext)


def test_your_tool_basic_case(mock_context: Mock) -> None:
    """Test basic functionality."""
    # Setup mock
    mock_session = Mock()
    mock_context.get_session.return_value = mock_session

    tool = YourTool(ToolContext())
    tool.context = mock_context

    # Execute tool
    result = tool.handle(YourToolArgs(session_id=SessionId("test")))

    # Assertions
    assert result.status == "success"
    assert result.data is not None


def test_your_tool_error_handling(mock_context: Mock) -> None:
    """Test error handling."""
    # Setup mock to raise error
    mock_context.get_session.side_effect = ToolExecutionError(
        "Session not found",
        code="SESSION_NOT_FOUND",
    )

    tool = YourTool(ToolContext())
    tool.context = mock_context

    # Should raise ToolExecutionError
    with pytest.raises(ToolExecutionError) as exc_info:
        tool.handle(YourToolArgs(session_id=SessionId("invalid")))

    assert exc_info.value.code == "SESSION_NOT_FOUND"

# if necessary
def test_your_tool_with_edge_cases(mock_context: Mock) -> None:
    """Test edge cases and boundary conditions."""
    # Test your tool with edge cases
    pass
```
---

### 10. Run Tests

Run tests:

---
```bash
# Run all tool tests
hatch run +py=3.12 test:test tests/_ai/tools

# Run your specific test
hatch run +py=3.12 test:test tests/_ai/tools/tools/test_your_tool.py

# Run with verbose output
hatch run +py=3.12 test:test tests/_ai/tools/tools/test_your_tool.py -v
```
---

### 11. Update Documentation

Add your tool to the user-facing documentation in `docs/guides/editor_features/tools.md`. Add a row to the appropriate category table:

---
```markdown
## Available tools

### [Appropriate Category]

| Tool | Description |
|------|-------------|
| **your_tool_name** | Brief description of what the tool does. Takes `param1` and `param2` parameters. Returns description of output. |
```
---

Choose the appropriate category:
- **Inspection**: Tools for exploring notebook structure and runtime
- **Data**: Tools for accessing variables and database information
- **Debugging**: Tools for finding and fixing issues
- **Reference**: Tools for accessing marimo documentation

## Best Practices

### Type Safety

- **Use dataclasses** for all input/output types
- **Add type hints** for all methods and attributes
- **Use TYPE_CHECKING** for imports only needed for type checking
- **Import from marimo types** (`SessionId`, `CellId_t`, etc.)
- **Keep types in your tool file** unless they're used by multiple tools—only add to `marimo/_ai/_tools/types.py` if shared across many files

### Documentation

- **Write clear docstrings** following the template
- **Document all Args** in the class docstring
- **Describe Returns** in the class docstring
- **Provide ToolGuidelines** to help AI assistants
- **Include examples** in docstrings when helpful

### Output Design

Design helpful outputs:

---
```python
return YourToolOutput(
    data=result,
    # Provide actionable next steps
    next_steps=[
        "Use get_cell_runtime_data to inspect cells",
        "Check errors with get_notebook_errors",
    ],
    # Optional user-facing message
    message="Found 5 items matching your query",
    # Optional metadata
    meta={"query_time": 0.5},
)
```
---

### Helper Methods

- **Prefix private methods with `_`**
- **Keep handle() method focused** on orchestration
- **Extract complex logic** into helper methods
- **Reuse ToolContext methods** instead of duplicating logic


## Common Pitfalls

### ❌ Don't: Duplicate ToolContext Logic

---
```python
# Bad: Reimplementing context logic
def handle(self, args: Args) -> Output:
    session = self.context.get_session(args.session_id)
    cell_notifications = session.session_view.cell_notifications
    errors = []
    for cell_id, op in cell_notifications.items():
        if op.output and op.output.channel == CellChannel.MARIMO_ERROR:
            errors.append(...)  # Duplicating error extraction
```
---

### ✅ Do: Use ToolContext Methods

---
```python
# Good: Using context methods
def handle(self, args: Args) -> Output:
    errors = self.context.get_notebook_errors(
        args.session_id,
        include_stderr=True
    )
```
---

### ❌ Don't: Raise Generic Exceptions

---
```python
# Bad: Using generic exceptions
if not found:
    raise ValueError("Not found")
```
---

### ✅ Do: Raise ToolExecutionError

---
```python
# Good: Structured error with metadata
if not found:
    raise ToolExecutionError(
        "Cell not found in session",
        code="CELL_NOT_FOUND",
        is_retryable=False,
        suggested_fix="Use get_lightweight_cell_map to find valid cell IDs",
    )
```
---

### ❌ Don't: Return Unstructured Data

---
```python
# Bad: Returning raw data
def handle(self, args: Args) -> Output:
    return {"data": [...], "count": 5}  # type: ignore
```
---

### ✅ Do: Use Typed Dataclass Output

---
```python
# Good: Structured output with SuccessResult
def handle(self, args: Args) -> Output:
    return YourToolOutput(
        data=[...],
        count=5,
        next_steps=["Review the results"],
    )
```
---

### ❌ Don't: Use TypedDict or Other Type Annotations

---
```python
# Bad: Using TypedDict for tool input/output
from typing import TypedDict

class YourToolArgs(TypedDict):
    session_id: str
    count: int
```
---

### ✅ Do: Use Dataclasses

---
```python
# Good: Using dataclasses as required
from dataclasses import dataclass

@dataclass
class YourToolArgs:
    session_id: SessionId
    count: int = 0
```
---

**Why?** The tool system requires dataclasses for proper serialization, validation, and compatibility with both backend and MCP contexts.

## Advanced Topics

### Async Tools

For operations that need async/await:

---
```python
class AsyncTool(ToolBase[Args, Output]):
    """Tool with async operations."""

    async def handle(self, args: Args) -> Output:  # type: ignore[override]
        """Note: Add type: ignore[override] for async handle."""
        session = self.context.get_session(args.session_id)
        result = await self._async_work(session)
        return Output(result=result)
```
---

### Tools with Side Effects

Generally it's better to avoid side effects in your tool. If it can't be avoided make sure to document side effects in guidelines:

---
```python
guidelines = ToolGuidelines(
    side_effects=[
        "Modifies notebook cells",
        "Triggers cell re-execution",
    ],
)
```
---

### Complex Return Types

Use nested dataclasses for complex outputs:

---
```python
@dataclass
class CellInfo:
    cell_id: str
    code: str


@dataclass
class ComplexOutput(SuccessResult):
    cells: list[CellInfo] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
```
---

## Review Checklist

Before submitting your tool:

- [ ] Tool class inherits from `ToolBase[ArgsT, OutT]`
- [ ] Input args are dataclasses ending with `Args`
- [ ] Output inherits from `SuccessResult` and ends with `Output`
- [ ] `handle()` method is implemented
- [ ] Tool is registered in `tools_registry.py`
- [ ] Args and Output added to `TOOL_IO_CLASSES` in `tests/_utils/test_msgspec_basestruct.py`
- [ ] Comprehensive docstring with Args/Returns
- [ ] `ToolGuidelines` provided (only if use cases are clear)
- [ ] Error handling uses `ToolExecutionError` for expected failures only
- [ ] Unit tests cover happy path and errors
- [ ] Tests mock `ToolContext` appropriately
- [ ] All tests pass
- [ ] Type hints are complete
- [ ] Documentation updated in `docs/guides/editor_features/tools.md`

## Additional Resources

- **Base Tool Class**: `marimo/_ai/_tools/base.py`
- **Tool Context**: `marimo/_ai/_tools/base.py` (`ToolContext`)
- **Exception Handling**: `marimo/_ai/_tools/utils/exceptions.py`
- **Type Definitions**: `marimo/_ai/_tools/types.py`
- **MCP Server Setup**: `marimo/_mcp/server/main.py`
- **Backend Tool Manager**: `marimo/_server/ai/tools/tool_manager.py`

## Questions?

If you have questions or run into issues:

1. Check existing tools in `marimo/_ai/_tools/tools/` for examples
2. Review tests in `tests/_ai/tools/tools/` for testing patterns
3. Ask in the marimo community channels
