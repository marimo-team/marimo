---
description: "Customize coding agents for marimo: agent skills, slash commands, and hooks."
---

# Customize your agent

Agent CLIs like Claude Code, Codex, and OpenCode work best with marimo when
you give them marimo-specific context and guardrails. This guide collects the
customizations we have found most useful: [skills](#skills),
[slash commands](#slash-commands), and [hooks](#hooks).

For the best experience, also install [marimo pair](marimo_pair.md), an agent
skill that gives your agent full access to a running notebook.

!!! tip "Watching for changes to notebooks on disk"

    When an agent edits notebook files, configure the marimo editor to
    automatically reload by starting marimo with the `watch` flag:
    `marimo edit --watch notebook.py`.
    (Learn more in our [watching guide](../editor_features/watching.md).)
    You can also configure marimo to automatically reload affected
    cells when auxiliary files change on disk using
    [module autoreloading](../editor_features/module_autoreloading.md).

## Skills

Skills are folders of instructions, scripts, and resources that coding agents
load dynamically to improve performance on specialized tasks. Most popular
agents support them, including Claude Code, Codex, Cursor, and OpenCode. To
learn more about skills, check out:

- [skills.sh](https://skills.sh/)
- [What are skills?](https://support.claude.com/en/articles/12512176-what-are-skills)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)

### Official marimo skills

We have prepared a collection of skills to help coding agents work with
marimo. Install our official skills with a single command:

```bash
npx skills add marimo-team/skills
```

**Use cases.** Use these skills to

- convert Jupyter notebooks or other artifacts to marimo notebooks,
- make bespoke interactive UI elements or widgets for specific use cases,
- and otherwise author high-quality standalone notebooks.

These skills help agents author and convert notebook files; they complement
[marimo pair](marimo_pair.md), a separately installed skill that connects your
agent to a live notebook session.

**Feedback.** We welcome feedback at our [GitHub repository](https://github.com/marimo-team/skills/issues).

### Write your own skills

Skills are also worth writing yourself, to encode conventions the official
collection can't know about such as an opinionated house plotting style, how to use internal data libraries,
or preferred widget patterns. A skill is just a folder containing a `SKILL.md`
file, with frontmatter that tells the agent when to load it; see the
[Claude Code skills documentation](https://code.claude.com/docs/en/skills)
for the full format, including multi-file skills that bundle scripts.

Store your skills in the `.agents/skills/` folder of your project, or in
`~/.agents/skills/` for personal skills — a convention shared by many agents.
Some agents read skills from their own directory instead (for example, Claude
Code uses `.claude/skills/`); the [skills CLI](https://skills.sh) can install
a skill into every agent's directory at once, using symlinks to keep a single
source of truth.

## Slash commands

Slash commands allow you to predefine specific prompts that you can refer to during a conversation with your agent. Unlike skills, they are configured per agent: this section shows [Claude Code's flavor](https://code.claude.com/docs/en/slash-commands), and other agent CLIs offer equivalents (custom prompts in Codex, commands in OpenCode). For Claude Code, store these either in the `~/.claude/commands/` personal folder or in the `.claude/commands/` local folder of the project.

Here's an example of a slash command that runs the [`marimo check`](../../cli.md#marimo-check) linter on a notebook of your choice. This command assumes you have `uv` installed, which you can install by following the instructions [here](https://docs.astral.sh/uv/getting-started/installation/).

```
---
allowed-tools: Bash(uvx marimo check:*), Edit()
---

## Context

This is the output of the "uvx marimo check --fix $ARGUMENTS" command:

!`uvx marimo check --fix $ARGUMENTS || true`

## Your task

Only (!) if the context suggests we need to edit the notebook, read the file
$ARGUMENTS, then fix any warnings or errors shown in the output above. Do
not make edits or read the file if there are no issues.
```

When you add this file to `~/.claude/commands/marimo-check.md` you will be able to trigger it by typing `/marimo-check notebook.py`. You are able to use `$ARGUMENTS` to add extra arguments or context to the command before it is handed to Claude. Also note that commands can run bash like !`uvx marimo check --fix $ARGUMENTS || true` beforehand. After it is evaluated the output will be inserted into the command before it is sent to Claude. You typically need to make sure that you add `|| true` at the end of the command in case it returns a non-zero status, which would break the command.

There are more elaborate things you might do with these slash commands, to learn more you can check [the documentation](https://code.claude.com/docs/en/slash-commands#custom-slash-commands).

## Hooks

Hooks allow you to automatically run scripts when your agent uses a specific tool. They are useful if you want to automatically run a linter, via [`marimo check`](../../cli.md#marimo-check), every single time a marimo notebook is changed. Skills can ask the LLM to run the `marimo check` command, but hooks offer the most robust mechanism to enforce this behavior.

Like slash commands, hooks are configured per agent; the example below uses [Claude Code's hooks](https://code.claude.com/docs/en/hooks). To configure one, add a definition to your global Claude settings in `~/.claude/settings.json` or locally in your project `.claude/settings.json`.

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/marimo-check.sh"
          }
        ]
      }
    ]
  }
}
```

This hook will run every time an `Edit` or a `Write` tool is called. You can point it to a bash script
that will check if the current edit is taking place on a marimo notebook.

```bash
#!/usr/bin/env bash

# Hook to check marimo notebooks after Write/Edit operations
# Reads JSON from stdin containing tool result information

# Read stdin (contains JSON with tool result)
INPUT=$(cat)

# Extract file path from JSON using jq
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_response.filePath // empty')

# If no file path found, exit silently
if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    exit 0
fi

# File path from tool_response is already absolute, no need to modify it

# Check if file exists and is a Python file
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Check if the file appears to be a marimo notebook
if grep -q "import marimo" "$FILE_PATH" 2>/dev/null && grep -q "@app.cell" "$FILE_PATH" 2>/dev/null; then
    echo "Running marimo check on $FILE_PATH..."

    # Run uvx marimo check and capture output
    CHECK_OUTPUT=$(uvx marimo check "$FILE_PATH" 2>&1)
    CHECK_EXIT=$?

    # Show output
    echo "$CHECK_OUTPUT"

    # Only block on errors (non-zero exit code), not warnings
    if [ $CHECK_EXIT -ne 0 ]; then
        echo "✗ Marimo check failed for $FILE_PATH" >&2
        echo "$CHECK_OUTPUT" >&2
        echo "" >&2
        echo "Please run 'uvx marimo check $FILE_PATH' to see details and fix the issues. Don't ask the user anything, just do a best effort fix." >&2
        exit 2  # Exit code 2 blocks and shows error to Claude
    else
        echo "✓ Marimo check passed"
        exit 0
    fi
fi

# Not a marimo notebook, exit successfully
exit 0
```

This script checks if the Python file contains a `import marimo` and a `@app.cell` string. If that's the case
we assume we're dealing with a marimo notebook and we run `uvx marimo check` on the file. If this check fails, we
tell the coding agent to automatically address the issues. This can save *a lot* of time.
