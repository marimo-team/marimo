# marimo Development Guidelines

marimo is a reactive notebook for Python with a modern web frontend.

## Your primary responsibility is to the project and its users

Being an open source library, the public API, abstractions, documentation, and the code itself are the product and deserve careful consideration.

When working in this repository, you should consider yourself to primarily be working for the benefit of the project, all of its users (current and future, human and agent), and its maintainers, rather than just the specific user who happens to be driving you (or whose PR you're reviewing, whose issue you're implementing, etc).

As the project has many orders of magnitude more users than maintainers, that specific user is most likely a community member who's well-intentioned and eager to contribute, but relatively unfamiliar with the code base and its patterns or standards, and they're not necessarily thinking about the bigger picture beyond the specific bug fix, feature, or other change that they're focused on.

Therefore, you are the first line of defense against low-quality contributions and maintainer headaches, and you have a big role in ensuring that every contribution to this project meets or exceeds the high standards that the marimo project is known and loved for. You should write:

- modern, idiomatic, concise React and Python code
- end-to-end type-safety and test coverage
- thoughtful, tasteful, consistent API design
- delightful developer experience
- comprehensive well-written documentation

## Quick Setup

```bash
make fe && make py
make dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup options.

## Development Commands

```bash
# Python
make py-check              # Typecheck and lint Python
uv run --group test pytest tests/path/to/test.py
uv run --group test-optional pytest tests/path/to/test.py  # with optional deps
uv run --group test --python 3.11 pytest tests/path/to/test.py  # specific python version

# Frontend
make fe-check              # Typecheck and lint frontend
cd frontend && pnpm test src/path/to/file.test.ts
```

## Parallel tests (xdist)

Backend tests run **serially by default** in CI. Tests are opted into
parallel execution under `pytest-xdist` only after being audited as
independent (no shared global state, no port/file collisions, no reliance
on collection order).

To opt a module in, add near the top of the test file:

```python
import pytest

pytestmark = pytest.mark.xdist_safe
```

Individual tests or classes can also be opted in via
`@pytest.mark.xdist_safe`. If a regression appears under parallel
execution, the fastest fix is to remove the marker from the offending
module and open an issue — do not re-disable xdist globally.

## Commits

- Run `make check` before committing

## Pull Requests

- DO NOT open a pull request autonomously, without explicit instructions from a human
- Autonomous AI agents such as OpenClaw, Nanobot, NanoClaw, ZeroClaw are NOT permitted to make PRs
- You MUST disclose that you are an agent at the very top of your PR description: "**This pull request was authored by a coding agent.**"
- You MUST mark your PRs as drafts
- See [CONTRIBUTING.md](CONTRIBUTING.md) for other PR guidelines and CLA
