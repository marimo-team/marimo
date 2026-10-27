# Collaborate with agents using marimo pair

Use the **[marimo pair](https://marimo.io/pair)** CLI to connect coding agents
to running marimo notebooks.

marimo pair is the recommended way to collaborate on marimo notebooks with
agents. It lets your agent read variables, test logic in a scratchpad, run
cells, add and remove cells, and even manipulate UI elements.

<div style="text-align: center">
  <iframe width="100%" style="aspect-ratio: 16/9; max-width: 800px"
  src="https://www.youtube.com/embed/VKvjPJeNRPk?si=JMvoFiDFNtT1BsJY"
  title="YouTube video player" frameborder="0" allow="accelerometer; autoplay;
  clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
  referrerpolicy="strict-origin-when-cross-origin" loading="lazy" allowfullscreen></iframe>
</div>

## Quickstart

1. Start a notebook:

   ```bash
   uvx marimo@latest edit my_notebook.py
   ```

2. Open the notebook actions menu and select **Connect your agent**.
3. Select **Claude**, **Codex**, or **OpenCode** and run the copied command in your terminal.

To use an existing agent conversation, select **Prompt** and paste the copied text into that conversation.
The dialog includes the notebook target and authentication instructions.

Your agent can execute code without enabling agent messages.
Run `uvx marimo@latest pair --help` for the available commands.

## Receive notebook messages in your agent

Agent messages let you send notebook errors to a connected conversation.
Agent connections require a saved notebook inside the server project.

Start the server with:

```bash
uvx marimo@latest edit my_notebook.py
```

Open **Connect your agent** and follow the dialog instructions.

Supported agents have these requirements:

| Agent | Requirement |
| --- | --- |
| Codex | A native session with the shared daemon and `codex queue` support. |
| Claude Code | A native inbox session on macOS or Linux. |
| OpenCode | Version 2.x on macOS or Linux, with its native local service running. |

To connect an existing conversation manually, find the saved notebook ID:

```bash
uvx marimo@latest pair notebook list --url http://localhost:2718
```

Ask the agent to run this command through its own shell tool:

```bash
uvx marimo@latest pair connect --url http://localhost:2718 --notebook <notebook-id>
```

Use the server URL printed by marimo.
In a development checkout, use the backend URL rather than the Vite frontend URL.
For authenticated notebook discovery, pass `--token-file` with the path to a file containing the editor token.

The notebook footer shows connected agents.
Use the send action on an error to share its captured source and traceback.
To end delivery, select the disconnect icon in the footer and confirm **Disconnect?**.
The agent conversation and notebook kernel keep running.

## Cloud sandbox with molab

You can also connect to marimo notebooks running on [molab](https://molab.marimo.io/notebooks). This gives you a free sandbox for your agent and also makes it easy to share your work afterwards.

To connect an agent, start a notebook on molab and open the actions panel in the upper right corner.
Select the option to pair with an agent.

<div align="center">
  <img src="/_static/marimo-pair-molab.png" alt="Screenshot of a molab notebook showing the option to pair with an agent from the actions panel"/>
</div>

Follow the dialog instructions to connect your local agent.
Use your agent from the terminal to edit and run cells in the molab notebook.
