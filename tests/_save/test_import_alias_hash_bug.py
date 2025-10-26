# Copyright 2024 Marimo. All rights reserved.
"""Test demonstrating the import alias hash bug for external marimo notebooks.

When a cached function is imported from an external marimo notebook, and that
function references a module by an alias, the hash doesn't account for which
actual module the alias points to. This causes cached functions that access
different modules to incorrectly produce the same hash.
"""

from __future__ import annotations

from marimo._ast.app import App


class TestExternalMarimoNotebookImportAliasHashBug:
    @staticmethod
    def test_external_cached_function_with_module_alias_bug() -> None:
        """
        BUG: A cached function imported from an external marimo notebook
        has the same hash as a locally-defined cached function, even though
        they access different modules (via the same alias name).

        Setup:
        - transitive_imports.py (external marimo notebook) defines:
          - imports module_1 as my_module (version "1.0.0")
          - @mo.cache function doesnt_have_namespace() that returns my_module.__version__

        - This test imports module_0 as my_module (version "0.0.0")
        - This test defines its own @mo.cache function that returns my_module.__version__

        BUG: Both functions have the same hash even though they return different values!
        """
        app = App()
        app._anonymous_file = True

        @app.cell
        def setup():
            import marimo as mo

            # Import module_0 with alias my_module (version "0.0.0")
            import tests._save.external_decorators.module_0 as my_module

            # Import cached function from external marimo notebook
            # That notebook imports module_1 as my_module (version "1.0.0")
            from tests._save.external_decorators.transitive_imports import (
                doesnt_have_namespace as external_func,
            )

            return mo, my_module, external_func

        @app.cell
        def define_local_func(mo, my_module):
            # Define a local cached function with the same logic
            # but using our my_module (module_0)
            @mo.cache
            def local_func():
                return my_module.__version__

            return (local_func,)

        @app.cell
        def check_bug(external_func, local_func, my_module):
            # Call both functions
            external_result = external_func()  # Returns "1.0.0" from module_1
            local_result = local_func()  # Returns "0.0.0" from module_0

            # Sanity check: verify we're actually getting different values
            assert external_result == "1.0.0", (
                f"Expected 1.0.0, got {external_result}"
            )
            assert local_result == "0.0.0", (
                f"Expected 0.0.0, got {local_result}"
            )
            assert external_result != local_result, (
                "Functions return different values"
            )
            assert external_result != my_module.__version__, (
                "External uses different module"
            )
            assert local_result == my_module.__version__, (
                "Local uses our module"
            )

            # Get their hashes
            external_hash = external_func._last_hash
            local_hash = local_func._last_hash

            assert external_hash != local_hash, (
                "Hashes should differ when accessing different modules"
            )

            return external_result, local_result, external_hash, local_hash

        _, defs = app.run()

        # Verify the bug is demonstrated
        assert defs["external_result"] != defs["local_result"]
        assert defs["external_hash"] == defs["local_hash"], (
            "BUG: Functions accessing different modules have the same hash!"
        )
