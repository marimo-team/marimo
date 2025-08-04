# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
import textwrap

from marimo._runtime.requests import ExecutionRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


class TestDecoratorImports:
    @staticmethod
    def test_has_shared_import(app) -> None:
        with app.setup:
            import marimo as mo
            from tests._save.external_decorators.transitive_imports import (
                has_import,
            )

        @app.cell
        def has_dep_works() -> tuple[int]:
            # matches test + use mo for lint
            assert has_import() == len([mo])

    @staticmethod
    def test_doesnt_have_shared_import(app) -> None:
        with app.setup:
            from tests._save.external_decorators.transitive_imports import (
                doesnt_have_import,
            )

        @app.cell
        def doesnt_have_dep_works() -> tuple[int]:
            # Counts modules on call.
            assert doesnt_have_import() == 2

    @staticmethod
    def test_has_dep_with_differing_name_works(app) -> None:
        for module in list(sys.modules.keys()):
            if module.startswith("tests._save.external_decorators"):
                del sys.modules[module]

        with app.setup:
            import marimo as mo
            import tests._save.external_decorators.module_0 as my_module
            from tests._save.external_decorators.transitive_imports import (
                doesnt_have_namespace as other,
                doesnt_have_namespace_pinned as other_pinned,
            )

        @app.function
        @mo.cache(pin_modules=True)
        def doesnt_have_namespace_pinned() -> None:
            return my_module.__version__

        @app.function
        @mo.cache
        def doesnt_have_namespace() -> None:
            return my_module.__version__

        @app.cell
        def has_dep_with_differing_name_works() -> tuple[int]:
            assert other() != my_module.__version__
            other_hash = other._last_hash
            assert doesnt_have_namespace() == my_module.__version__
            # By virtue of backwards compatibility, this is true.
            # TODO: Negate and fix.
            assert other_hash == doesnt_have_namespace._last_hash

        @app.cell
        def has_dep_with_differing_name_works_pinned() -> tuple[int]:
            assert other_pinned() != my_module.__version__
            other_hash_pinned = other_pinned._last_hash
            assert doesnt_have_namespace_pinned() == my_module.__version__
            assert other_hash_pinned != doesnt_have_namespace_pinned._last_hash

    @staticmethod
    async def test_decorator_in_kernel(
        lazy_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = lazy_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="setup",
                    code=textwrap.dedent(
                        """
                import marimo as mo
                import tests._save.external_decorators.module_0 as my_module
                from tests._save.external_decorators.transitive_imports import (
                    doesnt_have_namespace as other,
                    doesnt_have_namespace_pinned as other_pinned,
                )
                from tests._save.external_decorators.transitive_imports import (
                    doesnt_have_import,
                )
                from tests._save.external_decorators.transitive_imports import has_import
                """
                    ),
                ),
                exec_req.get(
                    """
                    @mo.cache(pin_modules=True)
                    def doesnt_have_namespace_pinned() -> None:
                        return my_module.__version__
                """
                ),
                exec_req.get(
                    """
                    @mo.cache
                    def doesnt_have_namespace() -> None:
                        return my_module.__version__
                """
                ),
                exec_req.get(
                    """
                    assert has_import() == 1
                    assert doesnt_have_import() == 2
                    assert other() != my_module.__version__
                    other_hash = other._last_hash
                    assert doesnt_have_namespace() == my_module.__version__
                    # By virtue of backwards compatibility, this is true.
                    # TODO: Negate and fix.
                    assert other_hash == doesnt_have_namespace._last_hash

                    assert other_pinned() != my_module.__version__
                    other_hash_pinned = other_pinned._last_hash
                    assert doesnt_have_namespace_pinned() == my_module.__version__
                    assert other_hash_pinned != doesnt_have_namespace_pinned._last_hash
                    resolved = True
                """
                ),
            ]
        )
        assert k.globals.get("resolved", False), k.stderr


class TestDecoratorTransitiveFns:
    @staticmethod
    async def test_impure_decorator_with_pure_dependencies(app) -> None:
        with app.setup:
            from tests._save.external_decorators.transitive_wrappers_1 import (
                pure_wrapped_impure,
            )
            from tests._save.external_decorators.transitive_wrappers_2 import (
                pure_wrapped_impure as pure_wrapped_impure_2,
            )

        @app.cell
        def _():
            result1 = pure_wrapped_impure()
            hash1 = pure_wrapped_impure._last_hash
            cache_type1 = pure_wrapped_impure.base_block.cache_type
            return result1, hash1, cache_type1

        @app.cell
        def _():
            result2 = pure_wrapped_impure_2()
            hash2 = pure_wrapped_impure_2._last_hash
            cache_type2 = pure_wrapped_impure_2.base_block.cache_type
            return result2, hash2, cache_type2

        @app.cell
        def check_results(
            result1, result2, hash1, hash2, cache_type1, cache_type2
        ):
            assert result1 == 1
            assert result2 == 2

            # The decorator itself is pure, but the function has impure dependencies
            # This should use ExecutionPath hashing, not ContentAddressed
            assert cache_type1 == "ExecutionPath", (
                f"Expected ExecutionPath, got {cache_type1}"
            )
            assert cache_type2 == "ExecutionPath", (
                f"Expected ExecutionPath, got {cache_type2}"
            )

            # Hashes should be different because the execution path changed
            # (due to different impure_dependency)
            assert hash1 != hash2, (
                f"Expected different hashes for different impure dependencies, "
                f"got {hash1} == {hash2}"
            )

    @staticmethod
    async def test_pure_decorator_with_impure_dependencies(app) -> None:
        with app.setup:
            from tests._save.external_decorators.transitive_wrappers_1 import (
                impure_wrapped_pure,
            )
            from tests._save.external_decorators.transitive_wrappers_2 import (
                impure_wrapped_pure as impure_wrapped_pure_2,
            )

        @app.cell
        def _():
            result1 = impure_wrapped_pure()
            hash1 = impure_wrapped_pure._last_hash
            cache_type1 = impure_wrapped_pure.base_block.cache_type

        @app.cell
        def _():
            result2 = impure_wrapped_pure_2()
            hash2 = impure_wrapped_pure_2._last_hash
            cache_type2 = impure_wrapped_pure_2.base_block.cache_type

        @app.cell
        def check_results(
            result1, result2, hash1, hash2, cache_type1, cache_type2
        ) -> None:
            assert result1 == 42
            assert result2 == 42

            # The decorator itself is pure, but the function has impure dependencies
            # This should use ExecutionPath hashing, not ContentAddressed
            assert cache_type1 == "ExecutionPath", (
                f"Expected ExecutionPath, got {cache_type1}"
            )
            assert cache_type2 == "ExecutionPath", (
                f"Expected ExecutionPath, got {cache_type2}"
            )

            # Hashes should be different because the execution path changed
            # (due to different impure_dependency)
            assert hash1 != hash2, (
                f"Expected different hashes for different impure dependencies, "
                f"got {hash1} == {hash2}"
            )
