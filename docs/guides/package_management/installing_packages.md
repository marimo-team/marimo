# Installing packages

marimo integrates with your package manager to install packages from the editor.
You can use the sidebar's package panel or accept an installation prompt when
an import is missing.

## Choose a package manager

For [projects](projects.md), marimo supports pip, uv, Poetry, Pixi, and Rye for
in-editor package management. Select your package manager in marimo's settings.

For [sandboxes](sandboxes.md), marimo supports uv and Pixi. Choose the tool with
a command-line option: `--sandbox` or `--sandbox=uv` for uv, and `--sandbox=pixi`
for Pixi.

## Where packages are installed

Packages installed through the editor go into the environment your notebook
uses. Where their requirements are recorded depends on your workflow.

In a **project**, package changes apply to every notebook using the shared
environment. With a project-aware package manager, marimo also updates the
shared requirements and lockfile through the tool's project commands.

In a **sandbox**, marimo updates the notebook's isolated environment and records
package requirements in its inline metadata, without affecting other notebooks.
The panel also lets you [edit metadata and sync the environment](sandboxes.md#edit-metadata-and-sync-the-environment).

!!! note "PyPI and Conda packages with Pixi"

    The package panel manages Conda dependencies in Pixi projects and PyPI
    dependencies in Pixi sandboxes. For PyPI packages in a project, use
    `pixi add --pypi` from the terminal. For Conda packages in a sandbox, use
    [Pixi-specific metadata or script commands](sandboxes.md#pixi-sandboxes).

!!! note "Resolving package names"

    Import names can differ from package names. marimo tries to infer the right
    package; if it guesses incorrectly, [file an issue](https://github.com/marimo-team/marimo/issues)
    or [contribute a mapping](https://github.com/marimo-team/marimo/blob/main/marimo/_runtime/packages/module_name_to_pypi_name.py).
