# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys


def test_has_shared_import(app) -> None:
    with app.setup:
        import marimo as mo
        from tests._save.decorator_imports.transitive_imports import has_import

    @app.cell
    def has_dep_works() -> tuple[int]:
        assert has_import() == len([mo])


def test_doesnt_have_shared_import(app) -> None:
    with app.setup:
        from tests._save.decorator_imports.transitive_imports import (
            doesnt_have_import,
        )

    @app.cell
    def doesnt_have_dep_works() -> tuple[int]:
        assert doesnt_have_import() == len([None, None])


def test_has_dep_with_differing_name_works(app) -> None:
    for module in list(sys.modules.keys()):
        if module.startswith("tests._save.decorator_imports"):
            del sys.modules[module]

    with app.setup:
        import marimo as mo
        import tests._save.decorator_imports.module_0 as my_module
        from tests._save.decorator_imports.transitive_imports import (
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
