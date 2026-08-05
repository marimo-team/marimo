---
description: "Three ways to use AI with marimo: pair coding agents with running notebooks, generate cells in the editor, and create notebooks from prompts."
---

# Generate notebooks with AI

There are three ways to use AI with marimo.

**Pair an agent with a running notebook (recommended).** Give agent CLIs like
Claude Code, Codex, and OpenCode full access to a live notebook with [marimo
pair](marimo_pair.md): your agent can read variables, test logic in a
scratchpad, run cells, and add or remove them. To teach your agent marimo's
conventions and automate common checks, see [customize your
agent](customize_your_agent.md).

**Use the marimo editor's built-in assistant.** The marimo editor comes with
[AI-assisted coding](../editor_features/ai_completion.md): a chat panel,
cell generation and refactoring, and inline copilots, connected to the LLM
provider of your choice. The assistant is data-aware, with access to the
values of variables in memory.

**Generate notebooks from a prompt.** Create entire notebooks from scratch at
the command line with [`marimo new`](text_to_notebook.md).

| Guide | Description |
|-------|-------------|
| [Pair with agents (marimo pair)](marimo_pair.md) | Collaborate on running notebooks with agent CLIs |
| [Customize your agent](customize_your_agent.md) | Skills, slash commands, and hooks |
| [The editor's AI assistant](../editor_features/ai_completion.md) | Generate and refactor cells, chat, and autocomplete in the editor |
| [Generate notebooks with marimo new](text_to_notebook.md) | Generate entire notebooks from a prompt |

Looking for lower-level integrations? marimo also exposes its [AI
tools](../editor_features/tools.md) over an [MCP
server](../editor_features/mcp.md), and can embed agents in the editor through
the experimental [agents panel](../editor_features/agents.md).
