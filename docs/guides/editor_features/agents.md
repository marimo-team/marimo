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

```bash
npx stdio-to-ws "npx @zed-industries/claude-code-acp" --port 3017
```

### Gemini Agent

Google's Gemini agent offers a limited free tier and login for more advanced features.

See login and authentication instructions in the [Gemini CLI documentation](https://github.com/google-gemini/gemini-cli?tab=readme-ov-file#-authentication-options).

**Connection command:**

```bash
npx stdio-to-ws "npx @google/gemini-cli --experimental-acp" --port 3019
```

## Connecting to an agent

1. **Start the agent server**: Run the connection command for your chosen agent in a terminal
2. **Enable the feature flag**: Enable the feature flag under the "Lab" section in the settings menu
3. **Open the agent panel**: Click the agents icon in marimo's sidebar
4. **Select your agent**: Choose the agent from the dropdown menu
5. **Start chatting**: The agent can now read and modify your notebooks

!!! tip "Terminal integration"

    If you have terminal access enabled in marimo, you can run agent connection commands directly from the agent panel using the terminal button.

## Custom agents

!!! info "Custom agents"

    Support for custom agents is coming soon. This will allow you to connect to your own ACP-compatible agents

## Troubleshooting

**Connection issues**: Ensure the agent server is running on the correct port before connecting in marimo.

**Permission requests**: Agents may request permission to read or write files. Review these carefully before approving.

**Session limits**: Currently, only one session per agent is supported for optimal performance.
