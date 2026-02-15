# Skills

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
    (Learn more in our [watching guide](/guides/editor_features/watching.md).)
    You can also configure marimo to automatically reload affected
    cells when auxiliary files change on disk using
    [module autoreloading](/guides/editor_features/module_autoreloading.md).

## What are skills?

Skills are folders of instructions, scripts, and resources that Claude and
other agents load dynamically to improve performance on specialized
tasks.

To learn more about skills, check out:

- [What are skills?](https://support.claude.com/en/articles/12512176-what-are-skills)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [skills.sh](https://skills.sh/)
