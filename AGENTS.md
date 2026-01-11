# marimo Development Guidelines

marimo is a reactive notebook for Python with a modern web frontend.

## Quick Setup

```bash
pixi shell
make fe && make py
make dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup options.

## Project Structure

```
marimo/           # Python backend - see marimo/AGENTS.md
frontend/         # React frontend - see frontend/AGENTS.md
tests/            # Python tests (mirrors marimo/ structure)
docs/             # Documentation site
```

## High-Level Architecture

**Backend (`/marimo/`)**: Reactive notebook runtime built on Starlette/Uvicorn
- `_ast/`: AST handling, cell parsing, dependency analysis
- `_runtime/`: Reactive execution engine, dataflow graph
- `_server/`: HTTP/WebSocket server, API endpoints, session management
- `_plugins/`: UI components (buttons, sliders, tables)
- `_sql/`: SQL cell support with multiple engine backends
- `_output/`: Output formatting and MIME types

**Frontend (`/frontend/src/`)**: Interactive UI built with React/TypeScript/Vite
- `core/`: Application state, cell management, runtime communication
- `codemirror/`: Code editor with Python/SQL support, completions
- `plugins/`: React implementations of UI components
- `components/`: Reusable UI components
- `hooks/`: Custom React hooks

**Communication**: WebSocket protocol (`/ws`) for real-time bidirectional messaging using typed operation-based messages.

## Development Commands

```bash
# Python
make py-check              # Typecheck and lint Python
uvx hatch run +py=3.12 test:test tests/path/to/test.py
uvx hatch run +py=3.12 test-optional:test tests/path/to/test.py  # with optional deps

# Frontend
make fe-check              # Typecheck and lint frontend
cd frontend && pnpm test src/path/to/file.test.ts
```

## Key Development Tips

- UI plugins require changes in both Python (`_plugins/`) and React (`plugins/`)
- The frontend communicates with the backend via WebSocket on `/ws`

## Pull Requests

- Run `make check` before committing
- See [CONTRIBUTING.md](CONTRIBUTING.md) for PR guidelines and CLA
