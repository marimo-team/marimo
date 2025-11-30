# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build, Lint, Test Commands

### First-time Setup
```bash
# Install pixi (https://github.com/prefix-dev/pixi) or use hatch directly
pixi shell  # or: hatch shell

# Install all dependencies
make fe && make py

# Start development servers (backend on 2718, frontend on 3000)
make dev
```

### Common Development Commands
```bash
# Build frontend only
make fe
# or for development mode (unminified):
NODE_ENV=development make fe -B

# Run all checks (lint, typecheck, format)
make check

# Run all tests
make test

# Frontend checks only
make fe-check    # lint + typecheck
make fe-lint
make fe-typecheck
make fe-test

# Python checks only
make py-check    # lint + format + typecheck
# or with hatch directly:
hatch run lint
hatch run format
hatch run typecheck:check

# Python tests
make py-test
# or run specific test:
hatch run +py=3.12 test:test tests/path/to/test.py
# or with optional dependencies:
hatch run +py=3.12 test-optional:test tests/path/to/test.py
# or run only changed tests:
hatch run +py=3.12 test:test --picked

# End-to-end tests (Playwright)
make e2e
# or interactively:
cd frontend && pnpm playwright test --ui

# Build docs
make docs
make docs-serve

# Storybook (UI component development)
make storybook
```

### Running marimo in Development Mode
```bash
# Backend with auto-restart on code changes
marimo -d edit --no-token

# Frontend hot-reloading (faster, less production-like)
cd frontend && pnpm dev

# Frontend watch mode (slower, closer to production)
cd frontend && pnpm build:watch
```

## Architecture Overview

marimo is a reactive Python notebook system with a Python backend and TypeScript/React frontend.

### Directory Structure

**Backend (Python):**
- `marimo/_ast/`: AST analysis and cell compilation
  - Parses cell code to extract variable definitions/references
  - `visitor.py`: Extracts defs/refs from Python AST
  - `sql_visitor.py`: Special handling for SQL cells
  - `codegen.py`: Generates `.py` file from notebook structure
  - `cell.py`: CellImpl class (cell state, config, code)
  - `app.py`: App class (notebook container)

- `marimo/_runtime/`: Reactive execution engine
  - `runtime.py`: Kernel class (main coordinator, ~474 lines)
  - `dataflow.py`: DirectedGraph (dependency tracking)
  - `executor.py`: Cell execution strategies (default, strict)
  - `requests.py`: Message types for kernel communication

- `marimo/_server/`: Web server (Starlette/uvicorn)
  - `sessions.py`: SessionManager (one session per client in edit mode)
  - `api/endpoints/`: REST and WebSocket endpoints
  - `main.py`: ASGI app creation
  - `start.py`: Server startup logic

- `marimo/_messaging/`: Communication protocol
  - `ops.py`: Operation types (kernel → frontend messages)
  - `types.py`: Core message types

- `marimo/_plugins/`: UI component system
  - `ui/_core/ui_element.py`: UIElement base class
  - `ui/_impl/`: Concrete UI elements (slider, dropdown, etc.)

- `marimo/_sql/`: SQL integration
  - `sql.py`: Main API (`mo.sql()`)
  - `engines/`: DuckDB, SQLAlchemy, etc.

**Frontend (TypeScript/React):**
- `frontend/src/core/`: Core logic
  - `cells/`: Cell state (Jotai atoms)
  - `websocket/`: WebSocket client
  - `kernel/`: Kernel message handling
  - `network/`: HTTP requests
  - `codemirror/`: Code editor

- `frontend/src/components/`: React components
- `frontend/src/plugins/`: UI plugin implementations

**Other:**
- `tests/`: Python unit tests (pytest)
- `frontend/src/__tests__/`: Frontend tests (Vitest)
- `frontend/e2e/`: End-to-end tests (Playwright)

### Reactive Notebook System

**How Reactivity Works:**

1. **Static Analysis**: When a cell is registered, `_ast/visitor.py` parses the code to extract:
   - `defs`: Variables defined (assignments, function defs, imports)
   - `refs`: Variables referenced
   - Special handling for SQL cells to extract table/view names

2. **Dependency Graph** (`_runtime/dataflow.py`):
   - DirectedGraph maintains:
     - `definitions`: variable name → defining cell
     - `children`: cell → cells that depend on it
     - `parents`: cell → cells it depends on
     - `siblings`: tracks multiply-defined variables (error state)
   - When a cell runs, graph identifies which descendants need re-execution

3. **Execution Modes**:
   - **Autorun** (default): Automatically run dependent cells when parent changes
   - **Lazy**: Mark dependent cells as "stale" instead of running (for expensive notebooks)

4. **No Hidden State Guarantee**:
   - All outputs determined solely by declared dependencies
   - Deleting a cell removes its variables from namespace
   - Re-running in any order produces same result

**Cell Execution Flow:**
1. User runs a cell → frontend sends `ExecutionRequest` via WebSocket
2. Kernel queues request in `control_queue`
3. `runtime.py` processes queue, identifies cells to run
4. `executor.py` executes cell code in shared namespace
5. Kernel sends `CellOp` messages back with results
6. Frontend updates cell state via Jotai atoms
7. Descendants automatically re-executed or marked stale

### Frontend-Backend Communication

**Protocol:**
- WebSocket at `/ws?session_id=...` (primary channel)
- Messages serialized with msgspec (binary or JSON)
- REST API at `/api/*` for non-real-time operations

**Key Message Types:**
- **Frontend → Backend**:
  - `ExecutionRequest`: Run cells
  - `SetUIElementValueRequest`: User interacted with UI element
  - `CodeCompletionRequest`: Autocomplete
  - `DeleteRequest`: Delete cells
  - `StopRequest`: Interrupt execution

- **Backend → Frontend**:
  - `CellOp`: Cell results (output, errors, console)
  - `Variables`: Variable updates (for variable explorer)
  - `RemoveUIElements`: Clean up stale UI elements
  - `KernelReady`: Initialization complete

**Frontend State Management:**
- Jotai atoms for fine-grained reactivity
- Separate atoms for:
  - `cellData`: Cell code, config
  - `cellRuntime`: Execution state, outputs
  - `cellHandles`: Editor refs, DOM elements

### UI Element System

**Architecture** (`_plugins/ui/_core/ui_element.py`):
```python
class UIElement[S, T]:
    # S: Frontend value type (JSON-serializable)
    # T: Python value type (transformed from S)
    def _convert_value(self, frontend_value: S) -> T: ...
```

**Reactivity:**
1. Create UI element in Python: `slider = mo.ui.slider(0, 10)`
2. Element rendered as web component in frontend
3. User interacts → frontend sends `SetUIElementValueRequest`
4. Backend updates element's internal state
5. Cells referencing `slider.value` automatically re-execute

**Registration:**
- Each element has unique `UIElementId`
- `UI_ELEMENT_REGISTRY` (frontend) tracks active elements
- Lifecycle tied to cell execution (cleanup when cell re-runs)

### SQL Integration

- **SQL Cells**: Special cell type (language="sql")
- **Python API**: `mo.sql("SELECT * FROM table")` executes SQL
- **Engines**: DuckDB (default, can query Python dataframes), SQLAlchemy, DBAPI 2.0
- **Variable Resolution**: Python variables accessible in SQL via f-strings
- **Dependency Tracking**: SQL results (tables/views) create Python variables in graph
- **Type System**: Separate namespace for SQL vs Python variables

### File Format

Marimo notebooks are pure Python files:
```python
import marimo

__generated_with = "0.18.1"
app = marimo.App(width="full")

@app.cell
def _():
    import marimo as mo
    return mo,

@app.cell
def _(mo):
    slider = mo.ui.slider(0, 10)
    return slider,
```

- Cells are functions decorated with `@app.cell`
- Dependencies inferred from function parameters and return values
- Configuration in decorators: `@app.cell(disabled=True, hide_code=True)`
- `codegen.py` generates this format from internal representation
- Format enables: git-friendly diffs, script execution, pytest integration

### Server Modes

**`marimo edit` (Edit Mode):**
- One session per file, persists across WebSocket disconnections
- File watching enabled (auto-reload on changes)
- Code editable in browser
- Session cached for faster startup

**`marimo run` (App Mode):**
- Multiple concurrent sessions per file
- Code hidden/read-only
- Session closed when WebSocket disconnects
- Suitable for deployment

## Python Development Guidelines

### Code Style
- Follow PEP 8
- Use type hints consistently
- Keep comments minimal and concise
- Prefer descriptive names over comments

### Testing
- Write pytest tests for all new functionality
- Tests use `pytest-asyncio` globally (no need for `@pytest.mark.asyncio`)
- Utilize snapshot testing where appropriate:
  ```python
  from tests.mocks import snapshotter
  snapshot = snapshotter(__file__)
  snapshot(filename, output)
  ```
- Focus on single use-case per test
- Minimal assertions per test
- Cover all edge cases

### Logging
Always use marimo's logger:
```python
from marimo import _loggers

LOGGER = _loggers.marimo_logger()
LOGGER.info("Message with params %s %s", param1, param2)  # % formatting, not f-strings
```

Log levels:
- `debug`: Diagnostic information
- `info`: Standard events
- `warn`: Unexpected but recoverable
- `error`: Functionality impaired

Never log sensitive information (tokens, passwords).

### Error Handling
- Use try-except for operations that can fail
- Follow established patterns with specific/custom exceptions
- Provide helpful error messages

## Frontend Development Guidelines

### Code Style
- TypeScript with proper typing for all new code
- Functional programming patterns (no classes)
- Use Jotai atoms for state (not `useState`/`useEffect`)
- Structure: main logic, component, types, utils

### Naming
- Directories: lowercase-with-dashes (`auth-wizard`)
- Named exports (no default exports)
- Logics: camelCase (`dashboardLogic`)
- Components: PascalCase (`DashboardMenu`)

### UI Development
- TailwindCSS for styling
- Use components from `@/components/ui` (Radix-based)
- React Hook Form + Zod for forms
- Vitest for testing

### Testing
- Test all edge cases
- Run: `cd frontend && pnpm test src/path/to/file.test.ts`

## Key Patterns

1. **Message-Passing Concurrency**: Kernel isolated in thread/process, communication via queues
2. **Execution Hooks**: `pre_execution_hooks`, `post_execution_hooks`, etc. enable extensibility
3. **Entry Points**: Custom executors, middleware via entry point registry
4. **WASM Support**: Pyodide runtime for browser execution (special handling in `_pyodide/`)
5. **LSP Integration**: Language Server Protocol for code completion/linting

## Troubleshooting

- Frontend changes not appearing: Rebuild with `make fe`
- TypeScript errors after Python changes: Regenerate OpenAPI client with `make fe-codegen`
- Test failures: Check if snapshots need updating with `make py-snapshots`
- WebSocket connection issues: Ensure both backend and frontend dev servers running
