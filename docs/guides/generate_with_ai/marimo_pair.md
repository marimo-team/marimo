# Collaborate with agents using marimo pair

Give your agent CLIs (such as Claude Code, Codex, and OpenCode) full access to running marimo notebooks with the **[marimo
pair](https://github.com/marimo-team/marimo-pair)** agent skill.

marimo pair is the recommended way to collaborate on marimo notebooks with
agents. It lets your agent read variables, test logic in a scratchpad, run
cells, add and remove cells, and even manipulate UI elements.

<div style="text-align: center">
  <iframe width="100%" style="aspect-ratio: 16/9; max-width: 800px"
  src="https://www.youtube.com/embed/VKvjPJeNRPk?si=JMvoFiDFNtT1BsJY"
  title="YouTube video player" frameborder="0" allow="accelerometer; autoplay;
  clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
  referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
</div>

## Quickstart

Install the skill with:

/// tab | install with npm

```bash
npx skills add marimo-team/marimo-pair
```

///

/// tab | install with uv

```bash
uvx deno -A npm:skills add marimo-team/marimo-pair
```

///

Then pair on your first notebook by pasting the following in your agent CLI:

```
/marimo-pair pair with me on my_notebook.py
```
