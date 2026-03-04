# Agents

!!! warning "Experimental Feature"
    Agents are currently experimental and under active development. Features and APIs may change.

marimo supports external AI agents that can interact with your codebase through the [Agent Client Protocol](https://agentclientprotocol.com/) (ACP). Agents can read and write marimo notebooks, helping you with coding tasks directly from the chat panel.

<video autoplay muted loop playsinline width="100%" height="100%" align="center">
  <source src="/_static/docs-claude-code-agent.mp4" type="video/mp4">
</video>

## Supported agents

marimo currently supports the following agents:

### Claude Code Agent

Claude Code Agent that uses your [Claude Code CLI subscription](https://docs.claude.com/en/docs/claude-code/overview) to help you with coding tasks.

**Installation and login:**

```bash
# Install
npm install -g @anthropic-ai/claude-code
# Login
claude
# Then type /login
```

**Connection command:**

=== "macOS/Linux"

    ```bash
    npx stdio-to-ws "npx @zed-industries/claude-code-acp" --port 3017
    ```

=== "Windows"

    ```bash
    npx stdio-to-ws "cmd /c npx @zed-industries/claude-code-acp" --port 3017
    ```

### Gemini Agent

Google's Gemini agent offers a limited free tier and login for more advanced features.

See login and authentication instructions in the [Gemini CLI documentation](https://github.com/google-gemini/gemini-cli?tab=readme-ov-file#-authentication-options).

**Connection command:**

=== "macOS/Linux"

    ```bash
    npx stdio-to-ws "npx @google/gemini-cli --experimental-acp" --port 3019
    ```

=== "Windows"

    ```bash
    npx stdio-to-ws "cmd /c npx @google/gemini-cli --experimental-acp" --port 3019
    ```

### Codex Agent

OpenAI's Codex agent uses [Codex CLI](https://github.com/openai/codex) via the [`@zed-industries/codex-acp`](https://github.com/zed-industries/codex-acp) adapter.

**Installation and login:**

```bash
# Install Codex CLI
npm install -g @openai/codex
# or: brew install --cask codex

# Login (or set OPENAI_API_KEY / CODEX_API_KEY)
codex
```

**Connection command:**

=== "macOS/Linux"

    ```bash
    npx stdio-to-ws "npx @zed-industries/codex-acp" --port 3021
    ```

=== "Windows"

    ```bash
    npx stdio-to-ws "cmd /c npx @zed-industries/codex-acp" --port 3021
    ```

### OpenCode Agent

[OpenCode](https://opencode.ai/) is an open source AI coding agent built for the terminal, but also supports ACP.

**Installation and login:**

```bash
# Install
npm install -g opencode-ai@latest

# Login
opencode
```

**Connection command:**

=== "macOS/Linux"

    ```bash
    npx stdio-to-ws "npx opencode-ai acp" --port 3023
    ```

=== "Windows"

    ```bash
    npx stdio-to-ws "cmd /c npx opencode-ai acp" --port 3023
    ```


Opencode supports many models, including local ones through Ollama, and can be configured via a configuration file.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:11434/v1"
      },
      "models": {
        "<model_name>": {
          "tools": true
        }
      }
    }
  }
}
```

If you choose to use a local model with Ollama, make sure that you set the maximum context length to be much higher than the 4K default. [This video tutorial](https://www.youtube.com/watch?v=4hUI2GF90nQ) explains how to set this up.

Opencode can also be configured to use remote models like those hosted by [OpenRouter](https://openrouter.ai/) or via [the Zen service](https://opencode.ai/docs/zen/). For more information on configuring OpenCode providers, see the [provider documentation](https://opencode.ai/docs/providers).


## Connecting to an agent

1. **Start the agent server**: Run the connection command for your chosen agent in a terminal
2. **Enable the feature flag**: Enable the feature flag under the "Lab" section in the settings menu
3. **Open the agent panel**: Click the agents icon in marimo's sidebar
4. **Select your agent**: Choose the agent from the dropdown menu
5. **Start chatting**: The agent can now read and modify your notebooks

!!! tip "Terminal integration"

    If you have terminal access enabled in marimo, you can run agent connection commands directly from the agent panel using the terminal button.

!!! tip "Auto-run on agent edits"

    By default, when an agent modifies your notebook, cells are marked as stale instead of running automatically. To have cells run automatically when the agent saves changes, add this configuration to your `pyproject.toml`:

    ```toml
    [tool.marimo.runtime]
    watcher_on_save = "autorun"
    ```

    This provides a more seamless experience when working with agents, as you'll see results immediately after the agent makes changes.

## Custom agents

!!! info "Custom agents"

    Support for custom agents is coming soon. This will allow you to connect to your own ACP-compatible agents

## Troubleshooting

**Connection issues**: Ensure the agent server is running on the correct port before connecting in marimo.

**Permission requests**: Agents may request permission to read or write files. Review these carefully before approving.

**Session limits**: Currently, only one session per agent is supported for optimal performance.
