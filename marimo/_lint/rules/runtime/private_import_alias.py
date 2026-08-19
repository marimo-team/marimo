# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from marimo._ast.parse import ast_parse
from marimo._ast.variables import is_local
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._schemas.serialization import CellDef


class PrivateImportAliasRule(LintRule):
    """MR004: Import aliased to a private (underscore-prefixed) name.

    This rule detects imports that are explicitly aliased to a name starting
    with an underscore more than once, e.g. `import os as _os`.

    ## What it does

    Scans import statements for an explicit `as` alias whose bound name starts
    with an underscore. This pattern is an undesirable but common workaround for
    marimo's global redefinition restriction with little tangible payoff.

    ## Why is this bad?

    Aliasing an import to a private name doesn't give the benefits users
    expect from it:

    - Imported modules are registered in `sys.modules` regardless of the
      name they're bound to, so marimo's private-variable cleanup doesn't
      free any extra memory.
    - Common imports like `numpy`, `pandas`, and `os` are usually needed in
      multiple cells, and giving them a private name defeats reuse while
      adding clutter.

    If the goal is to avoid the import polluting cell-to-cell dependencies, the
    fix is a setup cell, or import only cell instead. Setup cells run once,
    ahead of every other cell, while import only cells don't trigger
    re-execution of dependent cells (imports resolve independently of the
    notebook's reactive dataflow). Both of these approaches are preferable to
    aliasing imports to private names. You may even consider import only setup
    cells!

    ## Examples

    **Problematic:**
    ```python
    import os as _os

    _os.listdir(".")
    ```

    ```python
    import os as _os

    _os.getcwd()
    ```

    **Problematic:**
    ```python
    from collections import OrderedDict as _OrderedDict
    ```

    **Solution:**
    ```python
    # In the notebook's setup cell
    # or any import only cell.
    import os
    from collections import OrderedDict
    ```

    ```python
    os.listdir(".")
    ```

    ```python
    os.getcwd()
    ```

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Setup cell](https://docs.marimo.io/guides/understanding_errors/setup/)
    """

    code = "MR004"
    name = "private-import-alias"
    description = "Import aliased to a private (underscore-prefixed) name"
    severity = Severity.RUNTIME
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Check for private-aliased imports repeated across cells."""
        occurrences: dict[
            tuple[str, ...], list[tuple[CellDef, ast.alias]]
        ] = {}
        for cell in ctx.notebook.cells:
            if not cell.code.strip():
                continue

            try:
                tree = ast_parse(cell.code)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                for alias in node.names:
                    # `is_local` is the same notion of "private" that
                    # marimo's own name-mangling uses; it correctly excludes
                    # dunder-ish aliases (e.g. `__x`), which aren't given
                    # private-redefinition treatment.
                    if alias.asname is None or not is_local(alias.asname):
                        continue
                    key = self._import_key(node, alias)
                    occurrences.setdefault(key, []).append((cell, alias))

        for entries in occurrences.values():
            # Only flag if the same private alias is repeated across cells;
            # a single occurrence isn't the redefinition workaround this
            # rule is after.
            if len(entries) < 2:
                continue
            await self._report(entries, ctx)

    @staticmethod
    def _import_key(
        node: ast.Import | ast.ImportFrom, alias: ast.alias
    ) -> tuple[str, ...]:
        if isinstance(node, ast.ImportFrom):
            module = f"{'.' * node.level}{node.module or ''}"
            return ("from", module, alias.name, alias.asname or "")
        return ("import", alias.name, alias.asname or "")

    async def _report(
        self,
        entries: list[tuple[CellDef, ast.alias]],
        ctx: RuleContext,
    ) -> None:
        # Point to every occurrence, like MultipleDefinitionsRule does for
        # repeated variable definitions.
        lines = [cell.lineno + alias.lineno - 1 for cell, alias in entries]
        columns = [
            cell.col_offset + alias.col_offset + 1 for cell, alias in entries
        ]
        _, alias = entries[0]

        fix = (
            "This private import is repeated across multiple cells: "
            "consolidate the imports and drop the underscore. "
            "Consider moving the import into a setup cell (`with "
            "app.setup:`) or an import only cell"
        )

        diagnostic = Diagnostic(
            message=(
                f"Import of '{alias.name}' is aliased to the private "
                f"name '{alias.asname}' in multiple cells."
            ),
            line=lines,
            column=columns,
            code=self.code,
            name=self.name,
            severity=self.severity,
            fixable=self.fixable,
            fix=fix,
        )
        await ctx.add_diagnostic(diagnostic)
