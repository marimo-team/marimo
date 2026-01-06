Many coding agents let you customise the marimo editing experience. This page lists some worthwhile utilities from different providers and we also provide a compelling use-case for each related to marimo development.

## Claude

### Slash Commands

[Slash Commands](https://code.claude.com/docs/en/slash-commands) allow you to predefine specific prompts that you can refer to during a conversation with Claude. You store these skills either in the `~/.claude/commands/` personal folder or in the `.claude/commands/` local folder of the project.

Here's an example of a slash command that runs the `marimo check` linter of a notebook of your choice.

```md
---
allowed-tools: Bash(uvx marimo check)
description: Check a marimo notebook
---

## Context

This is the output of the marimo check command:

!`uvx marimo check $ARGUMENTS`

## Your task

Address any warnings or errors that appear for the marimo notebook.
```

You would store a command like this either in the `~/.claude/skills/` personal folder or in the `.claude/skills/` local folder of the project.

There are more elaborate things you might do with these slash commands, to learn more you can check [the documentation](https://code.claude.com/docs/en/slash-commands#custom-slash-commands).

### Skills

[Skills](https://code.claude.com/docs/en/skills#agent-skills) are similar to commands, but you don't trigger them manually. You define them and then let Claude use them when it thinks it's relevant. You store these skills either in the `~/.claude/skills/` personal folder or in the `.claude/skills/` local folder of the project.

As an example, this is what the start of a skill might look like to help you design anywidgets for your marimo notebooks:

```md
---
name: anywidget-generator
description: Generate anywidget components for marimo notebooks.
---

# Put a full prompt here
```

You would store this file in a path like `~/.claude/skills/anywidget-generator/SKILL.md`. The frontmatter gives the LLM just enough context to know when to trigger it and will only read the full prompt when it's needed.

You can also choose to expand these skills by referring to a script that it can run, to learn more about that check the [multi-file documentation](https://code.claude.com/docs/en/skills#example:-multi-file-skill-structure).


### Hooks

[Hooks](https://code.claude.com/docs/en/hooks) allow you to automatically run scripts when Claude uses a specific tool. They are useful if you want to automatically run a linter, via `marimo check`, every single time a marimo notebook is changed. Our default `Claude.md` file already points out to the LLM that it should run the `marimo check` command but hooks offer the most robust mechanism to enforce this behavior.

To configure a hook, you can add a definition to your global Claude settings in `~/.claude/settings.json` or locally in your project `.claude/settings.json`.

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
#!/bin/bash

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

The script if the edited file contains a `import marimo` and a `@app.cell` string in the file. If that's the case
we assume we're dealing with a marimo notebook and we run `uvx marimo check` on the file. If this check fails, we
tell the llm to automatically address the issues. This can save *a lot* of time.
