# Skills

Skills are folders of instructions and resources that teach an AI assistant
how to do something well. marimo supports skills in two directions:

1. **Skills for external agents** editing your marimo notebooks — e.g. Claude
   Code or pi in a terminal. See [Skills for external agents](#skills-for-external-agents).
2. **Skills for marimo's built-in AI** — dropped into a conventional
   directory and automatically injected into the system prompt of every AI
   chat and refactor call. See [Skills for marimo's built-in AI](#skills-for-marimos-built-in-ai).

Both follow the same [Agent Skills format](https://agentskills.io), so a
skill authored for one works in the other.

## Skills for external agents

We have prepared a collection of skills to help coding agents work with marimo.
Install our official skills with a single command:

```bash
npx skills add marimo-team/skills
```

**Use cases.** Use these skills to

- convert Jupyter notebooks or other artifacts to marimo notebooks,
- make bespoke interactive UI elements or widgets for specific use cases,
- and otherwise author high-quality standalone notebooks.

**Feedback.** We welcome feedback at our [GitHub repository](https://github.com/marimo-team/skills/issues).

!!! tip "Watching for changes to notebooks on disk"

    When using marimo with Claude Code, configure the marimo editor to
    automatically reload when Claude edits your notebook by starting
    marimo with the `watch` flag: `marimo edit --watch notebook.py`.
    (Learn more in our [watching guide](../editor_features/watching.md).)
    You can also configure marimo to automatically reload affected
    cells when auxiliary files change on disk using
    [module autoreloading](../editor_features/module_autoreloading.md).

## What are skills?

Skills are folders of instructions, scripts, and resources that Claude and
other agents load dynamically to improve performance on specialized
tasks.

To learn more about skills, check out:

- [What are skills?](https://support.claude.com/en/articles/12512176-what-are-skills)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [skills.sh](https://skills.sh/)

## Skills for marimo's built-in AI

You can also write skills for the AI assistant inside marimo itself. When a
skill is discovered on disk, its body is appended to the system prompt of
every chat and refactor call — you don't need to invoke it manually; the
model sees it on every turn.

### Where marimo looks for skills

By default, marimo scans the following directories (later entries override
earlier ones when two skills share a name):

| Path | Purpose |
|------|---------|
| `~/.marimo/skills/` | Your personal skills, available in every notebook |
| `~/.agents/skills/` | Cross-agent skills shared with Claude Code / pi |
| `<cwd>/.marimo/skills/` | Skills checked into the notebook's repo |
| `<cwd>/.agents/skills/` | Project-local cross-agent skills |

Skills authored for Claude Code or pi (in `.agents/skills/`) work in
marimo unchanged.

### Skill format

Each skill lives in its own folder with a `SKILL.md` file:

```
.marimo/
  skills/
    viz/
      SKILL.md
    sql-style/
      SKILL.md
```

A `SKILL.md` has optional frontmatter plus a markdown body:

```markdown
---
name: viz
description: >-
    Use when the user asks for visualizations, charts, or plots. Prefer
    altair for statistical charts; return chart objects as the last
    expression.
---

# Visualization guidance

- Use `alt.Chart(df)` directly on polars/pandas dataframes.
- Return the chart object as the last expression of the cell.
- Add tooltips where they aid exploration.
```

If you omit the frontmatter, the skill name defaults to the folder name and
the description defaults to the first paragraph of the body.

### Configuring skill paths

Add extra directories via `marimo.toml`:

```toml
[ai.skills]
# Additional directories to scan. ``~`` is expanded; relative paths
# resolve against the notebook's working directory.
custom_paths = ["~/team-skills", "./packages/notebook-skills"]

# Set to false to disable the default paths above.
include_default_paths = true
```

### Inspecting loaded skills

The `GET /api/ai/skills` endpoint returns every skill marimo currently sees
(name, description, origin, approximate token cost), which is useful for
tooling and for confirming that a newly-added skill is actually being
picked up.

### When to reach for a skill vs. a custom rule

- A single-line preference (e.g. "use polars over pandas") fits fine in
  [custom rules](../editor_features/ai_completion.md#custom-rules) — a
  skill would be overkill.
- A multi-paragraph guideline tied to a specific trigger ("only when the
  user asks about visualizations") is what skills are for — the
  `description` tells the model when the guidance applies so it doesn't
  dilute every call.
