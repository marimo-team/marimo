---
description: "Using AI with marimo notebooks."
---

# Generate notebooks with AI

There are three main ways to manipulate marimo notebooks with AI.

**Use agents with running notebooks.** Give agents like
Claude Code and OpenCode full access to running notebooks with [marimo
pair](marimo_pair.md). Paired agents can do anything you can do and more: read
variables, test logic in a scratchpad, run cells, read UI element values, and
more.

**Use the marimo editor's built-in assistant.** The marimo editor comes with
[AI-assisted coding](../editor_features/ai_completion.md): a chat panel,
cell generation and refactoring, and inline copilots, connected to the LLM
provider of your choice. The assistant is data-aware, with access to the
values of variables in memory.

**Use skills.**  Install [skills](skills.md) for specific tasks, such
as converting notebooks from Jupyter to marimo.


| Guide | Description |
|-------|-------------|
| [marimo pair](marimo_pair.md) | Collaborate on running notebooks with coding agents |
| [In-editor AI assistance](../editor_features/ai_completion.md) | Generate and refactor cells, chat, and autocomplete in the editor |
| [Skills](skills.md) | Skills for coding agents |
