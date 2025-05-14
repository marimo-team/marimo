# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from marimo._ast.app import App
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


class TestHash:
    @staticmethod
    def test_pure_hash(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = [1, 2, 3]
                Z = len(Y)
            assert cache._cache.cache_type == "Pure"
            return Y, Z

    @staticmethod
    def test_content_hash(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            a = 1
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = a
            assert cache._cache.cache_type == "ContentAddressed"
            return (Y,)

    # Note: Hash may change based on byte code, so pin to particular version
    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_content_reproducibility(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "haIqC9yzlTaNo-ClmY11Kvtiv08oQPz3-SlnOLfhJYM"

            return expected_hash, persistent_cache, MockLoader

        @app.cell
        def one(expected_hash, persistent_cache, MockLoader) -> None:
            _a = 1
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                _X = 10 + _a
            assert _X == 7
            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, _cache._cache.hash

        @app.cell
        def two(expected_hash, persistent_cache, MockLoader) -> tuple[int]:
            # The same as cell one, but with this comment
            _a = 2 - 1

            # Some white space
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                # More Comments
                _X = 10 + _a
            assert _X == 7
            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, _cache._cache.hash
            # and a post block difference
            Z = 11
            return (Z,)

    @staticmethod
    def test_execution_hash(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            non_primitive = [object()]

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = 8 + len(non_primitive)
            assert cache._cache.cache_type == "ContextExecutionPath"
            return (Y,)

    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_execution_reproducibility(app) -> None:
        # Rewrite changes the AST, breaking the hash
        app._pytest_rewrite = False

        @app.cell
        def imports() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            return persistent_cache, MockLoader

        @app.cell
        def load() -> tuple[int]:
            shared = [None, object()]
            return shared

        @app.cell
        def one(persistent_cache, MockLoader, shared) -> tuple[int]:
            _a = [1, object()]
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                _X = 10 + _a[0] - len(shared)  # Comment
            assert _X == 7
            # Cannot be reused/ shared, because it will change the hash.
            assert (
                _cache._cache.hash
                == "jjufTYhiG11S6Fe3odSETSvYbYObdSRZDYhWXFlCaXE"
            ), _cache._cache.hash
            assert _cache._cache.cache_type == "ContextExecutionPath"
            return

        @app.cell
        def two(persistent_cache, MockLoader, shared) -> tuple[int]:
            # The same as cell one, but with this comment
            _a = [
                1,  # Comment
                object(),
            ]
            # Some white space
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                # More Comments
                _X = 10 + _a[0] - len(shared)
            assert _X == 7
            assert (
                _cache._cache.hash
                == "jjufTYhiG11S6Fe3odSETSvYbYObdSRZDYhWXFlCaXE"
            ), _cache._cache.hash
            assert _cache._cache.cache_type == "ContextExecutionPath"
            # and a post block difference
            Z = 11
            return (Z,)

    @staticmethod
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_execution_reproducibility_different_cell_order(app) -> None:
        # NB. load is last for cell order difference.
        # Rewrite changes the AST, breaking the hash
        app._pytest_rewrite = False

        @app.cell
        def one(persistent_cache, MockLoader, shared) -> tuple[int]:
            _a = [1, object()]
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                _X = 10 + _a[0] - len(shared)  # Comment
            assert _X == 7
            # Cannot be reused/ shared, because it will change the hash.
            assert (
                _cache._cache.hash
                == "jjufTYhiG11S6Fe3odSETSvYbYObdSRZDYhWXFlCaXE"
            ), _cache._cache.hash
            assert _cache._cache.cache_type == "ContextExecutionPath"
            return

        @app.cell
        def two(persistent_cache, MockLoader, shared) -> tuple[int]:
            # The same as cell one, but with this comment
            _a = [
                1,  # Comment
                object(),
            ]
            # Some white space
            with persistent_cache(
                name="one", _loader=MockLoader(data={"_X": 7})
            ) as _cache:
                # More Comments
                _X = 10 + _a[0] - len(shared)
            assert _X == 7
            assert (
                _cache._cache.hash
                == "jjufTYhiG11S6Fe3odSETSvYbYObdSRZDYhWXFlCaXE"
            ), _cache._cache.hash
            assert _cache._cache.cache_type == "ContextExecutionPath"
            # and a post block difference
            Z = 11
            return (Z,)

        @app.cell
        def imports() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            return persistent_cache, MockLoader

        @app.cell
        def load() -> tuple[int]:
            shared = [None, object()]
            return shared

    @staticmethod
    def test_transitive_content_hash() -> None:
        app1 = App()
        app1._anonymous_file = True
        app1._pytest_rewrite = True

        @app1.cell
        def _():
            import marimo as mo

            return mo

        @app1.cell
        def _():
            value = False

        @app1.cell
        def cache_1(args, mo):
            with mo.persistent_cache("cache_bug") as cache:
                output = args.value
            assert cache.cache_type == "ExecutionPath"

        @app1.cell
        def _(value):
            class Unhashable:
                def __eq__(self, other):
                    return isinstance(other, Unhashable)

                __hash__ = None  # Makes instances unhashable

            args = Unhashable()
            args.value = value
            return (args,)

        app2 = App()
        app2._anonymous_file = True
        app2._pytest_rewrite = True

        @app2.cell
        def _():
            import marimo as mo

            return mo

        @app2.cell
        def _():
            value = True

        @app2.cell
        def cache_2(args, mo):
            with mo.persistent_cache("cache_bug") as cache:
                output = args.value
            assert cache.cache_type == "ExecutionPath"

        @app2.cell
        def _(value):
            class Unhashable:
                def __eq__(self, other):
                    return isinstance(other, Unhashable)

                __hash__ = None  # Makes instances unhashable

            args = Unhashable()
            args.value = value
            return (args,)

        _, defs1 = app1.run()
        _, defs2 = app2.run()

        assert defs1["cache"]._cache.hash != defs2["cache"]._cache.hash
        assert defs1["output"] != defs2["output"]

    @staticmethod
    def test_function_ui_content_hash(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            slider = mo.ui.slider(1, 10)

            def shared() -> str:
                return "x" * slider.value

            return persistent_cache, MockLoader, shared, slider

        @app.cell
        def one(persistent_cache, MockLoader, shared, slider) -> tuple[Any]:
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                _Y = len(shared())
            slider._update(7)
            assert cache._cache.cache_type == "ExecutionPath"
            return (cache,)

        @app.cell
        def two(persistent_cache, MockLoader, shared, cache) -> tuple[Any]:
            with persistent_cache(name="two", _loader=MockLoader()) as cache2:
                _Y = len(shared())
            assert cache2._cache.cache_type == "ExecutionPath"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)

    @staticmethod
    def test_function_state_content_hash(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            state, set_state = mo.state(0)

            def shared(state) -> str:
                return "x" * state()

            return persistent_cache, MockLoader, shared, state, set_state

        @app.cell
        def one(
            persistent_cache, MockLoader, shared, state, set_state
        ) -> tuple[Any]:
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                _Y = len(shared(state))
            set_state(1)
            assert cache._cache.cache_type == "ContentAddressed"
            return (cache,)

        @app.cell
        def two(
            persistent_cache, MockLoader, shared, state, cache
        ) -> tuple[Any]:
            with persistent_cache(name="two", _loader=MockLoader()) as cache2:
                _Y = len(shared(state))
            assert cache2._cache.cache_type == "ContentAddressed"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)

    @staticmethod
    def test_function_state_content_hash_distinct(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import cache

            state, _set_state = mo.state(0)

            @cache
            def check_type(v) -> str:
                return str(type(v))

            a = check_type(0)
            b = check_type(state)
            assert a != b, (a, "!=", b)
            assert a == "<class 'int'>", a
            assert "State" in b, b
            return a, b

    @staticmethod
    def test_transitive_execution_path_when_state_dependent(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            state, set_state = mo.state(0)

            def shared() -> str:
                return "x" * state()

            return persistent_cache, MockLoader, shared, state, set_state

        @app.cell
        def one(
            persistent_cache, MockLoader, shared, set_state, state
        ) -> tuple[Any]:
            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                _Y = len(shared())
            assert _Y == state()
            set_state(1)
            assert cache._cache.cache_type == "ExecutionPath"
            return (cache,)

        @app.cell
        def two(
            persistent_cache, MockLoader, shared, cache, state
        ) -> tuple[Any]:
            with persistent_cache(name="two", _loader=MockLoader()) as cache2:
                _Y = len(shared())
            assert _Y == state()
            assert cache2._cache.cache_type == "ExecutionPath"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)

    @staticmethod
    def test_version_pinning(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import marimo as mo
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            mo.__version__ = "0.0.0"

            return mo, persistent_cache, MockLoader

        @app.cell
        def one(mo, persistent_cache, MockLoader) -> tuple[Any]:
            with persistent_cache(
                name="one", _loader=MockLoader(), pin_modules=True
            ) as cache:
                _Y = len(mo.__version__)
            mo.__version__ = "0.0.1"
            assert cache._cache.cache_type == "ContentAddressed"
            return (cache,)

        @app.cell
        def two(mo, persistent_cache, MockLoader, cache) -> tuple[Any]:
            with persistent_cache(
                name="two", _loader=MockLoader(), pin_modules=True
            ) as cache2:
                _Y = len(mo.__version__)
            mo.__version__ = "0.0.0"
            assert cache2._cache.cache_type == "ContentAddressed"
            assert cache2._cache.hash != cache._cache.hash
            return (cache2,)


class TestDataHash:
    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.numpy.has(),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_numpy_hash(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import numpy as np

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "w_Bjhpz2xMVQC6Y61GgqB8O80u_UyoJ-1xQmJU3j0Gg"
            return MockLoader, persistent_cache, expected_hash, np

        @app.cell
        def one(MockLoader, persistent_cache, expected_hash, np) -> tuple[int]:
            _a = np.ones((16, 16)) * 2
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = np.sum(_a)
            one = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

        @app.cell
        def two(MockLoader, persistent_cache, expected_hash, np) -> tuple[int]:
            _a = np.ones((16, 16)) + np.ones((16, 16))

            with persistent_cache(name="two", _loader=MockLoader()) as _cache:
                _A = np.sum(_a)
            two = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (two,)

        @app.cell
        def three(one, two) -> None:
            assert one == two
            assert one == 512

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("jax"),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_jax_hash(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            from jax import numpy as np

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "aAL9QNoQIQ1zOJgm_xDbHG63Bc4Atnpn58pGW9x9A_A"
            return MockLoader, persistent_cache, expected_hash, np

        @app.cell
        def one(MockLoader, persistent_cache, expected_hash, np) -> tuple[int]:
            _a = np.ones((16, 16)) * 2
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = np.sum(_a)
            one = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

        @app.cell
        def two(MockLoader, persistent_cache, expected_hash, np) -> tuple[int]:
            _a = np.ones((16, 16)) + np.ones((16, 16))

            with persistent_cache(name="two", _loader=MockLoader()) as _cache:
                _A = np.sum(_a)
            two = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (two,)

        @app.cell
        def three(one, two) -> None:
            assert one == two
            assert one == 512

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("torch"),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_torch_hash(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import torch

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "stIOtiKIn4yscvKd-uK6mbmZpWzzfGm8Ccz7mvnRrnI"
            return MockLoader, persistent_cache, expected_hash, torch

        @app.cell
        def one(
            MockLoader, persistent_cache, expected_hash, torch
        ) -> tuple[int]:
            _a = torch.ones((16, 16)) * 2
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = torch.sum(_a)
            one = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

        @app.cell
        def two(
            MockLoader, persistent_cache, expected_hash, torch
        ) -> tuple[int]:
            _a = torch.ones((16, 16)) + torch.ones((16, 16))

            with persistent_cache(name="two", _loader=MockLoader()) as _cache:
                _A = torch.sum(_a)
            two = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (two,)

        @app.cell
        def three(one, two) -> None:
            assert one == two
            assert one == 512

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("torch"),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_torch_device_hash(app) -> None:
        # Utilizing the "meta" device should give similar cross device behavior
        # as gpu.

        @app.cell
        def load() -> tuple[Any]:
            import torch

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "iV5v_cNAxBPqe8tNJnI5volNORTH_gyhKuIvHcG_cds"
            return MockLoader, persistent_cache, expected_hash, torch

        @app.cell
        def one(
            MockLoader, persistent_cache, expected_hash, torch
        ) -> tuple[int]:
            _a = torch.ones((16, 16), device="meta") * 2
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = torch.sum(_a)
            one = _A

            assert _cache._cache.cache_type == "ContextExecutionPath", (
                _cache._cache.cache_type
            )
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("skbio"),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_skibio_hash(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            from copy import copy

            from skbio import DNA

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "ggxwHLzWcyDQltN_Zq0_zYVP_w86a9AAQLQwleAMuH8"
            return MockLoader, persistent_cache, expected_hash, DNA, copy

        @app.cell
        def one(
            MockLoader, persistent_cache, expected_hash, copy, DNA
        ) -> tuple[int]:
            strand = DNA("GATTACA")
            # Siblings not bound to be in-valid
            sibling = copy(strand)
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                assert strand == sibling

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("pandas"),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_dataframe(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import numpy as np
            import pandas as pd

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "wtrS6NoH2AOH3DnWm7wooK4Bgw8TmMotgMbiY0bu5as"
            return MockLoader, persistent_cache, expected_hash, np, pd

        @app.cell
        def one(
            MockLoader, persistent_cache, expected_hash, np, pd
        ) -> tuple[int]:
            _a = {
                "A": [1, 2, 3],
                "column names don't contribute to hash": [4, 5, 6],
                "the dict order does though": [7, 8, 9],
            }
            _a = pd.DataFrame(_a) ** 2
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = np.sum(_a["A"])
            one = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

        @app.cell
        def two(
            MockLoader, persistent_cache, expected_hash, np, pd
        ) -> tuple[int]:
            _a = {"A": [1, 4, 9], "B": [16, 25, 36], "C": [49, 64, 81]}
            _a = pd.DataFrame(_a)

            with persistent_cache(name="two", _loader=MockLoader()) as _cache:
                _A = np.sum(_a["A"])
            two = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (two,)

        @app.cell
        def three(one, two) -> None:
            assert one == two
            assert one == 14

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("pandas"),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_dataframe_object(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import numpy as np
            import pandas as pd

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "RbeMLx994_-kB9rF2ebi6mFMbCW_S6-Q41MsrgJgwUA"
            return MockLoader, persistent_cache, expected_hash, np, pd

        @app.cell
        def one(
            MockLoader, persistent_cache, expected_hash, np, pd
        ) -> tuple[int]:
            _a = {
                "A": [2, 8, 18],
                "B": ["a", "a", "a"],
                "C": [14, 16, 18],
            }
            _a = pd.DataFrame(_a)
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = np.sum(_a["A"])
            one = _A

            assert _cache._cache.cache_type == "ContextExecutionPath"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("polars"),
        reason="optional dependencies not installed",
    )
    # Pin to a particular python version for differences in underlying library
    # implementations / memory layout.
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_polars_dataframe(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import polars as pl

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "rC6YiNsuaZKQ1JqMgSRa0iyEDwi7ZTl6InABjuM0RDY"
            return MockLoader, persistent_cache, expected_hash, pl

        @app.cell
        def one(MockLoader, persistent_cache, expected_hash, pl) -> tuple[int]:
            _a = {
                "A": [1, 2, 3],
                "column names don't contribute to hash": [4, 5, 6],
                "the dict order does though": [7, 8, 9],
            }
            _a = pl.DataFrame(_a).select(pl.all() ** 2)
            with persistent_cache(name="one", _loader=MockLoader()) as _cache:
                _A = _a.select(pl.col("A").sum()).item()
            one = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (one,)

        @app.cell
        def two(MockLoader, persistent_cache, expected_hash, pl) -> tuple[int]:
            _a = {"A": [1, 4, 9], "B": [16, 25, 36], "C": [49, 64, 81]}
            _a = pl.DataFrame(_a)

            with persistent_cache(name="two", _loader=MockLoader()) as _cache:
                _A = _a.select(pl.col("A").sum()).item()
            two = _A

            assert _cache._cache.cache_type == "ContentAddressed"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            return (two,)

        @app.cell
        def three(one, two) -> None:
            assert one == two
            assert one == 14

    @staticmethod
    @pytest.mark.skipif(
        not DependencyManager.has("polars"),
        reason="optional dependencies not installed",
    )
    @pytest.mark.skipif(
        "sys.version_info < (3, 12) or sys.version_info >= (3, 13)"
    )
    def test_polars_object(app) -> None:
        @app.cell
        def load() -> tuple[Any]:
            import polars as pl

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            expected_hash = "QzGgcNS-eEP58qkkFphgAOJNKEpoTNcXhJ-L2exXzr4"
            return MockLoader, persistent_cache, expected_hash, pl

        @app.cell
        def two(MockLoader, persistent_cache, expected_hash, pl) -> tuple[int]:
            _a = {
                "A": [2, 8, 18],
                "B": ["a", "a", "a"],
                "C": [14, 16, 18],
            }
            _a = pl.DataFrame(_a)

            with persistent_cache(name="two", _loader=MockLoader()) as _cache:
                _A = _a.select(pl.col("A").sum()).item()

            assert _cache._cache.cache_type == "ContextExecutionPath"
            assert _cache._cache.hash == expected_hash, (
                f"expected_hash != {_cache._cache.hash}"
            )
            assert _A == 28
            return (two,)


class TestDynamicHash:
    @staticmethod
    async def test_transitive_state_hash(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get("import marimo as mo; from pathlib import Path"),
                exec_req.get("value, set_value = mo.state(False)"),
                exec_req.get("""
                class Unhashable:
                    def __eq__(self, other):
                        return isinstance(other, Unhashable)

                    __hash__ = None  # Makes instances unhashable

                args = Unhashable()
                args.value = value
                """),
                exec_req.get(f"""
                with mo.persistent_cache("cache", save_path=Path("{tmp_path.as_posix()}")) as cache:
                    output = args.value
                """),
            ]
        )
        assert not k.errors
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        assert not k.globals["cache"]._cache.hit

        hash_1 = k.globals["cache"]._cache.hash
        output_1 = k.globals["output"]

        await k.run([exec_req.get("set_value(True)")])
        assert not k.errors
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        assert not k.globals["cache"]._cache.hit

        hash_2 = k.globals["cache"]._cache.hash
        output_2 = k.globals["output"]

        assert hash_1 != hash_2
        assert output_1 != output_2


class TestSideEffects:
    @staticmethod
    async def test_side_effect_cache_different(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                from pathlib import Path

                state, set_state = mo.state(0)
                hashes = []
                """),
                exec_req.get("""
                with mo.cache("prim") as prim_cache:
                    non_primitive = [object(), len(hashes)]
                state
                """),
                exec_req.get("""
                with mo.persistent_cache("get_v", save_path=tmp_path_fixture) as v_cache:
                    v = non_primitive[1]
                """),
            ]
        )
        await k.run(
            [
                exec_req.get("""
                if len(hashes) < 1:
                    assert non_primitive[1] == 0
                    set_state(1)
                hashes.append((v_cache.cache_type, v_cache._cache.hash))
                hashes.append((prim_cache.cache_type, prim_cache._cache.hash))
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        v = k.globals["v"]
        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]
        assert len(hashes) == 4
        assert hashes[1] != hashes[3]
        assert hashes[0] != hashes[2]
        assert non_primitive[1] == 2 == v

    @staticmethod
    async def test_side_effect_cache_context(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                from pathlib import Path

                state, set_state = mo.state(0)
                hashes = []
                """),
                exec_req.get("""
                with mo.cache("prim") as prim_cache:
                    non_primitive = [object(), len(hashes)]

                with mo.persistent_cache("get_v", save_path=tmp_path_fixture) as v_cache:
                    v = non_primitive[1]
                state
                """),
            ]
        )
        await k.run(
            [
                exec_req.get("""
                if len(hashes) < 1:
                    assert non_primitive[1] == 0
                    set_state(1)
                hashes.append((v_cache.cache_type, v_cache._cache.hash))
                hashes.append((prim_cache.cache_type, prim_cache._cache.hash))
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        v = k.globals["v"]
        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]
        assert len(hashes) == 4
        assert hashes[1] != hashes[3]
        assert hashes[0] != hashes[2]
        assert non_primitive[1] == 2 == v

    @staticmethod
    async def test_side_effect_exception(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                from pathlib import Path

                state, set_state = mo.state(1)
                hashes = []
                """),
                exec_req.get("""
                non_primitive = [object(), 0]
                ref = 1
                1 / state() # Throw an exception when 0
                non_primitive = [object(), 1]
                """),
            ]
        )
        assert not k.stderr.messages, k.stderr
        await k.run(
            [
                req := exec_req.get("""
                with mo.persistent_cache("get_v", save_path=tmp_path_fixture) as v_cache:
                    v = non_primitive[1] + ref
                """),
                exec_req.get("""
                if len(hashes) < 1:
                    set_state(0)
                hashes.append((v_cache.cache_type, v_cache._cache.hash, v))
                """),
            ]
        )
        await k.run([req])

        assert not k.stdout.messages, k.stdout
        assert "ZeroDivisionError" in str(k.stderr), k.stderr

        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]

        v = k.globals["v"]

        assert len(hashes) == 2
        assert non_primitive[1] == 0
        assert v == 1
        assert hashes[0] != hashes[1]

    @staticmethod
    async def test_side_effect_decorator_different(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                import weakref

                state, set_state = mo.state(0)
                hashes = []
                """),
                exec_req.get("""
                @mo.cache
                def prim_cache():
                    return [weakref.ref(object), len(hashes)]
                non_primitive = prim_cache()
                state
                """),
                exec_req.get("""
                @mo.cache
                def v_cache():
                    return non_primitive[1]
                v = v_cache()
                """),
            ]
        )
        await k.run(
            [
                exec_req.get("""
                if len(hashes) < 1:
                    assert non_primitive[1] == 0
                    set_state(1)
                hashes.append(v_cache._last_hash)
                hashes.append(prim_cache._last_hash)
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        v = k.globals["v"]
        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]
        assert len(hashes) == 4
        assert hashes[1] != hashes[3]
        assert hashes[0] != hashes[2]
        assert non_primitive[1] == 2 == v

    @staticmethod
    async def test_side_effect_decorator_context(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        # Actually doesn't test side effects, because there's
        # no "context" level hash for functions. Placed here incase the
        # functionality does change in the future.
        await k.run(
            [
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                import weakref

                state, set_state = mo.state(0)
                hashes = []
                """),
                exec_req.get("""
                @mo.cache
                def prim_cache():
                    return [weakref.ref(object), len(hashes)]
                non_primitive = prim_cache()

                @mo.cache
                def v_cache():
                    return non_primitive[1]
                v = v_cache()
                state
                """),
            ]
        )
        await k.run(
            [
                exec_req.get("""
                if len(hashes) < 1:
                    assert non_primitive[1] == 0
                    set_state(1)
                hashes.append(v_cache._last_hash)
                hashes.append(prim_cache._last_hash)
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert k.stderr.messages, k.stderr
        assert "Content addressed hash could not be utilized" in str(
            k.stderr
        ), k.stderr

    @staticmethod
    async def test_side_effect_decorator_exception(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                from pathlib import Path

                state, set_state = mo.state(1)
                hashes = []
                """),
                exec_req.get("""
                non_primitive = [object(), 0]
                ref = 1
                1 / state() # Throw an exception when 0
                non_primitive = [object(), 1]
                """),
            ]
        )
        assert not k.stderr.messages, k.stderr
        await k.run(
            [
                req := exec_req.get("""
                @mo.cache
                def v_cache():
                    return non_primitive[1] + ref
                v = v_cache()
                """),
                exec_req.get("""
                if len(hashes) < 1:
                    set_state(0)
                hashes.append((v_cache._last_hash, v))
                """),
            ]
        )
        await k.run([req])

        assert not k.stdout.messages, k.stdout
        assert "ZeroDivisionError" in str(k.stderr), k.stderr

        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]

        v = k.globals["v"]

        assert len(hashes) == 2
        assert non_primitive[1] == 0
        assert v == 1
        assert hashes[0] != hashes[1]

    @staticmethod
    async def test_side_effect_file(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                mo.watch._file._TEST_SLEEP_INTERVAL = 0.01
                from pathlib import Path

                hashes = []
                """),
                exec_req.get("""
                f = mo.watch.file(tmp_path_fixture / "test.txt")
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        await k.run(
            [
                exec_req.get("""
                f
                non_primitive = [object(), len(hashes), f.exists()]
                """),
                exec_req.get("""
                with mo.persistent_cache("get_v", save_path=tmp_path_fixture) as v_cache:
                    v = non_primitive[1]
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        await k.run(
            [
                r := exec_req.get("""
                if len(hashes) < 1:
                    assert non_primitive[1] == 0
                hashes.append((v_cache.cache_type, v_cache._cache.hash))
                """),
            ]
        )
        (tmp_path / "test.txt").touch()
        await asyncio.sleep(0.25)
        await k.run([])
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        v = k.globals["v"]
        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]
        assert len(hashes) == 2
        assert hashes[0] != hashes[1]
        assert non_primitive[1] == 1 == v

    @staticmethod
    async def test_side_effect_directory(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                mo.watch._directory._TEST_SLEEP_INTERVAL = 0.01
                from pathlib import Path

                hashes = []
                """),
                exec_req.get("""
                (tmp_path_fixture / "test_dir").mkdir(parents=True, exist_ok=True)
                d = mo.watch.directory(tmp_path_fixture / "test_dir")
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        await k.run(
            [
                exec_req.get("""
                non_primitive = [object(), len(hashes), d.glob("*")]
                """),
                exec_req.get("""
                with mo.persistent_cache("get_v", save_path=tmp_path_fixture) as v_cache:
                    v = non_primitive[1]
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        await k.run(
            [
                r := exec_req.get("""
                if len(hashes) < 1:
                    assert non_primitive[1] == 0
                hashes.append((v_cache.cache_type, v_cache._cache.hash))
                """),
            ]
        )
        (tmp_path / "test_dir" / "test.txt").write_text("test")
        await asyncio.sleep(0.25)
        await k.run([])
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        v = k.globals["v"]
        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]
        assert len(hashes) == 2
        assert hashes[0] != hashes[1]
        assert non_primitive[1] == 1 == v

    @staticmethod
    async def test_side_effect_file_ref(
        k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                from tests._save.loaders.mocks import MockLoader
                import marimo as mo
                from pathlib import Path

                hashes = []
                """),
                exec_req.get(
                    'u = mo.watch.file(tmp_path_fixture / "test.txt")'
                ),
                exec_req.get("""
                non_primitive = [object(), len(hashes)]
                with mo.cache("prim") as prim_cache:
                    # unused, but should trigger side effect
                    u
                """),
                exec_req.get("""
                with mo.persistent_cache("get_v", save_path=tmp_path_fixture) as v_cache:
                    v = non_primitive[1]
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        await k.run(
            [
                exec_req.get("""
                if len(hashes) < 1:
                    assert non_primitive[1] == 0
                    u.write_text("test")
                hashes.append((v_cache.cache_type, v_cache._cache.hash))
                hashes.append((prim_cache.cache_type, prim_cache._cache.hash))
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        v = k.globals["v"]
        hashes = k.globals["hashes"]
        non_primitive = k.globals["non_primitive"]
        # Docs warn not to use write directly since RC can occur, causing double
        # event.
        assert len(hashes) == 4
        assert hashes[1] != hashes[3]
        assert hashes[0] != hashes[2]
        assert non_primitive[1] == 2 == v
