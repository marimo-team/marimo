# Copyright 2026 Marimo. All rights reserved.
"""Emit the compiled notebook from a :class:`~marimo._build.plan.Plan`.

For each cell, the plan tells us exactly one of four things to do:

- :py:attr:`CellKind.SETUP`    -> emit the original ``with app.setup`` block;
- :py:attr:`CellKind.LOADER`   -> replace the body with code that reads the
  precomputed artifact;
- :py:attr:`CellKind.ELIDED`   -> drop the cell from the output entirely;
- :py:attr:`CellKind.VERBATIM` -> emit the original cell unchanged.

A synthetic helper cell containing the loader functions actually used
by the notebook is prepended to the output. The catalog:

- ``marimo_artifact_path(filename)`` -> absolute path string used in
  SQL ``read_parquet('...')`` calls and by the Python loaders below;
- ``marimo_load_parquet(filename)``  -> polars DataFrame;
- ``marimo_load_json(filename)``     -> the deserialized JSON value.

Helper names deliberately don't start with ``_``: marimo treats
single-underscore-prefixed names as cell-local and mangles them, so a
``_marimo_load_parquet`` would be invisible to the loader cells that
need it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._ast.cell import CellConfig
from marimo._ast.codegen import generate_filecontents
from marimo._build.plan import CellKind

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._ast.app import InternalApp
    from marimo._ast.app_config import _AppConfig
    from marimo._build.plan import Plan
    from marimo._build.serialize import ArtifactKind
    from marimo._types.ids import CellId_t


# Name of the synthetic helper cell prepended to every compiled
# notebook. Users should not have an original cell by this name.
HELPER_CELL_NAME = "_marimo_build_loaders"

# One-time-use helper definitions, keyed by the symbol they introduce.
# Order in this dict is the source order they're emitted in (Python
# 3.7+ preserves insertion order). ``marimo_load_*`` depend on
# ``marimo_artifact_path``, so it must come first.
#
# Imports live inside the function bodies so they don't leak as
# cell-level defs and don't shadow user-defined names like ``Path``.
HELPER_DEFS: dict[str, str] = {
    "marimo_artifact_path": """\
def marimo_artifact_path(filename: str) -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parent / filename)
""",
    "marimo_load_parquet": """\
def marimo_load_parquet(filename: str):
    import polars

    return polars.read_parquet(marimo_artifact_path(filename))
""",
    "marimo_load_json": """\
def marimo_load_json(filename: str):
    import json

    with open(marimo_artifact_path(filename)) as f:
        return json.load(f)
""",
}


@dataclass(frozen=True)
class CellArtifact:
    """One persisted def of a LOADER cell."""

    def_name: str
    filename: str
    kind: ArtifactKind


def emit_compiled_notebook(
    *,
    app: InternalApp,
    plan: Plan,
    artifacts: Mapping[CellId_t, list[CellArtifact]],
    config: _AppConfig | None = None,
) -> str:
    """Emit the compiled notebook source.

    The plan determines the kind of every cell; this function walks
    cells in original order, emits accordingly, and prepends a helper
    cell containing exactly the loader functions the notebook
    references (or no helper cell at all if the notebook has no
    LOADERs).
    """
    graph = app.graph
    cell_manager = app.cell_manager

    codes: list[str] = []
    names: list[str] = []
    cell_configs: list[CellConfig] = []
    helpers_used: set[str] = set()

    for cell_id in cell_manager.cell_ids():
        cell = graph.cells[cell_id]
        kind = plan.kind(cell_id)
        if kind is CellKind.ELIDED:
            continue
        if kind is CellKind.LOADER:
            code, refs = _build_loader(
                cell.language, artifacts.get(cell_id, [])
            )
            helpers_used |= refs
        else:
            # SETUP and VERBATIM both keep their original source.
            # generate_filecontents extracts the setup cell by name.
            code = cell.code
        codes.append(code)
        names.append(cell_manager.cell_name(cell_id))
        cell_configs.append(cell.config)

    helper_code = _helper_cell_code(helpers_used)
    if helper_code is not None:
        # ``generate_filecontents`` extracts the setup cell by name, so
        # the helper just needs to come before any user cell in this
        # list — index 0 always works.
        codes.insert(0, helper_code)
        names.insert(0, HELPER_CELL_NAME)
        cell_configs.insert(0, CellConfig(hide_code=True))

    return generate_filecontents(
        codes=codes,
        names=names,
        cell_configs=cell_configs,
        config=config,
    )


def _build_loader(
    language: str, cell_artifacts: list[CellArtifact]
) -> tuple[str, set[str]]:
    """Loader cell source plus the helper names it references.

    Returns ``("pass", set())`` for the (defensive) case of a LOADER
    cell with no artifacts, so the compiled file still parses.
    """
    if not cell_artifacts:
        return "pass", set()

    # Single-def SQL dataframe: keep it as ``mo.sql(...)`` so the
    # compiled cell still renders as SQL in the editor.
    if (
        language == "sql"
        and len(cell_artifacts) == 1
        and cell_artifacts[0].kind == "dataframe"
    ):
        artifact = cell_artifacts[0]
        code = (
            f"{artifact.def_name} = mo.sql(\n"
            f'    f"SELECT * FROM '
            f"read_parquet('{{marimo_artifact_path('{artifact.filename}')}}')"
            f'"\n'
            f")"
        )
        return code, {"marimo_artifact_path"}

    lines: list[str] = []
    refs: set[str] = set()
    for artifact in cell_artifacts:
        loader = (
            "marimo_load_parquet"
            if artifact.kind == "dataframe"
            else "marimo_load_json"
        )
        lines.append(f'{artifact.def_name} = {loader}("{artifact.filename}")')
        refs.add(loader)
    # The Python loaders both delegate to marimo_artifact_path, so it
    # rides along whenever either is needed.
    if refs:
        refs.add("marimo_artifact_path")
    return "\n".join(lines), refs


def _helper_cell_code(helpers_used: set[str]) -> str | None:
    """Source for the helper cell, or ``None`` if no helpers are needed.

    Functions are emitted in :data:`HELPER_DEFS` order so that
    ``marimo_artifact_path`` precedes the loaders that call it.
    """
    if not helpers_used:
        return None
    return "\n\n".join(
        body for name, body in HELPER_DEFS.items() if name in helpers_used
    )
