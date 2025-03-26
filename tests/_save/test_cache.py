# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import sys
import textwrap
import warnings

import pytest

from marimo._ast.app import App
from marimo._runtime.requests import ExecutionRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


class TestScriptCache:
    @staticmethod
    def test_cache_miss() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            # Check top level import
            from marimo import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = 8
                X = 7
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert cache._loader._saved
            assert not cache._loader._loaded
            return X, Y, persistent_cache

        # Coverage's trace override conflicts with cache introspection. Letting
        # the first test fail seems to fix this issue.
        # TODO: fix with_setup to properly manage both traces.
        try:
            app.run()
        except Exception as e:
            if "--cov=marimo" not in sys.argv:
                raise e
            pytest.mark.xfail(
                reason="Coverage conflict with cache introspection"
            )

    @staticmethod
    def test_cache_hit(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            with persistent_cache(
                name="one", _loader=MockLoader(data={"X": 7, "Y": 8})
            ) as cache:
                Y = 9
                X = 10
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert not cache._loader._saved
            assert cache._loader._loaded
            return X, Y, persistent_cache

    @staticmethod
    def test_cache_loader_api(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from tests._save.loaders.mocks import MockLoader

            with MockLoader.cache("one", data={"X": 7, "Y": 8}) as cache:
                Y = 9
                X = 10
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert not cache._loader._saved
            assert cache._loader._loaded
            return X, Y

    @staticmethod
    def test_cache_hit_whitespace(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            # fmt: off
            with persistent_cache(name="one",
                                  _loader=MockLoader(
                                    data={"X": 7, "Y": 8})
                                  ) as cache:  # noqa: E501
                Y = 9
                X = 10
            # fmt: on
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert not cache._loader._saved
            assert cache._loader._loaded
            return X, Y, persistent_cache

    @staticmethod
    def test_cache_linebreak(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            # fmt: off
            # issues 3332, 2633
            with persistent_cache("one", _loader=_loader) as cache:
                b = [
                    8
                ]
            # fmt: on
            assert b == [8]
            assert cache._cache.defs == {"b": [8]}

    @staticmethod
    def test_cache_if_block_and_break(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            # fmt: off
            b = [2]
            if True:
              with persistent_cache("if", _loader=_loader):  # noqa: E111
                  b = [  # noqa: E111
                      7
                  ]
            # fmt: on
            assert b == [7]

    @staticmethod
    def test_cache_if_block(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            b = 2
            if True:
                with persistent_cache("if", _loader=_loader):
                    b = 8
            assert b == 8

    @staticmethod
    def test_cache_else_block(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            if False:
                b = 2
            else:
                with persistent_cache("else", _loader=_loader):
                    b = 8
            assert b == 8

    @staticmethod
    def test_cache_elif_block(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            if False:
                b = 2
            elif True:
                with persistent_cache("else", _loader=_loader):
                    b = 8
            assert b == 8

    @staticmethod
    def test_cache_with_block(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from contextlib import contextmanager

            @contextmanager
            def called(v):
                assert v
                yield 1

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            with called(True):
                with persistent_cache("else", _loader=_loader):
                    b = 8
            assert b == 8

    @staticmethod
    def test_cache_with_block_inner(app) -> None:
        @app.cell
        def one() -> tuple[int]:
            from contextlib import contextmanager

            @contextmanager
            def called(v):
                assert v
                yield 1

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            with persistent_cache("else", _loader=_loader):
                with called(True):
                    b = 8
            assert b == 8

    @staticmethod
    def test_cache_same_line_fails() -> None:
        from marimo._ast.transformers import BlockException

        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            def call(v):
                assert v

            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()
            # fmt: off
            with persistent_cache("else", _loader=_loader): call(False)  # noqa: E701
            # fmt: on

        with pytest.raises(BlockException):
            app.run()

    @staticmethod
    def test_cache_in_fn_fails() -> None:
        from marimo._ast.transformers import BlockException

        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.loaders.mocks import MockLoader

            _loader = MockLoader()

            def call():
                with persistent_cache("else", _loader=_loader):
                    return 1

            call()

        with pytest.raises(BlockException):
            app.run()


class TestAppCache:
    async def test_cache_miss(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                from marimo._save.save import persistent_cache
                from tests._save.loaders.mocks import MockLoader

                with persistent_cache(
                  name="one", _loader=MockLoader()
                ) as cache:
                    Y = 9
                    X = 10
                Z = 3
                """
                    ),
                ),
            ]
        )
        assert k.globals["Y"] == 9
        assert k.globals["X"] == 10
        assert k.globals["Z"] == 3

    async def test_cache_hit(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                from marimo._save.save import persistent_cache
                from tests._save.loaders.mocks import MockLoader

                with persistent_cache(
                    name="one", _loader=MockLoader(data={"X": 7, "Y": 8})
                ) as cache:
                    Y = 9
                    X = 10
                Z = 3
                """
                    ),
                ),
            ]
        )
        assert k.globals["X"] == 7
        assert k.globals["Y"] == 8
        assert k.globals["Z"] == 3

    async def test_cache_one_line(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
        from marimo._save.save import persistent_cache
        from tests._save.loaders.mocks import MockLoader

        with persistent_cache(name="one", _loader=MockLoader(data={"X": 1})):
            X = 1
        Y = 2
                """
                    ),
                ),
            ]
        )
        assert k.errors == {}
        assert k.errors == {}
        assert k.globals["X"] == 1
        assert k.globals["Y"] == 2

    async def test_cache_comment_line(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                from marimo._save.save import persistent_cache
                from tests._save.loaders.mocks import MockLoader

                with persistent_cache(name="one", _loader=MockLoader()):
                    # Comment

                    # whitespace
                    X = 1 # Comment
                    Y = 2
                """
                    ),
                ),
            ]
        )
        assert not k.stderr.messages, k.stderr
        assert k.errors == {}
        assert k.errors == {}
        assert k.globals["X"] == 1
        assert k.globals["Y"] == 2


class TestStateCache:
    async def test_set_state_works_normally(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        create_class = """
        class A:
            def __eq__(self, other):
                # shouldn't be triggered by marimo
                import sys
                sys.exit()
        a = A()
        """
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get(create_class),
                exec_req.get("state, set_state = mo.state(None)"),
                exec_req.get("x = state()"),
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from tests._save.loaders.mocks import MockLoader

                    with persistent_cache(
                        name="cache", _loader=MockLoader()
                    ) as cache:
                        set_state(a)
                    """
                ),
            ]
        )

        assert id(k.globals["x"]) == id(k.globals["a"])
        # Set as a def, because it is stateful
        assert id(k.globals["cache"]._cache.defs["set_state"]) == id(
            k.globals["a"]
        )

    async def test_set_state_hits_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("state, set_state = mo.state(7)"),
                exec_req.get("rerun, set_rerun = mo.state(True)"),
                exec_req.get("impure = []"),
                exec_req.get("redo = rerun()"),
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from tests._save.loaders.mocks import MockLoader

                    with persistent_cache(
                        name="cache", _loader=MockLoader(),
                    ) as cache:
                        set_state(9)

                    if redo:
                        set_rerun(False)
                    impure.append(cache._cache.hash)
                    """
                ),
            ]
        )

        # Should be hit on rerun, because set_state does not have a state
        # itself.
        assert len(k.globals["impure"]) == 2
        assert k.globals["impure"][0] == k.globals["impure"][1]
        assert k.globals["state"]() == 9

    async def test_set_state_invalidates(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("impure = []; impure_value = []"),
                exec_req.get("state, set_state = mo.state(0)"),
                exec_req.get("x = state()"),
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from tests._save.loaders.mocks import MockLoader

                    with persistent_cache(
                        name="cache", _loader=MockLoader()
                    ) as cache:
                        a = x + 1

                    if len(impure) < 4:
                        impure.append(cache._cache.hash)
                        impure_value.append(a)
                        set_state(a % 3)
                    """
                ),
            ]
        )

        assert len(k.globals["impure"]) == 4
        assert len(set(k.globals["impure"])) == 3
        assert k.globals["impure"][0] == k.globals["impure"][-1]

        assert set(k.globals["impure_value"]) == {1, 2, 3}

        assert k.globals["a"] == 2
        assert k.globals["state"]() == 1

    async def test_set_state_loads(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("state, set_state = mo.state(11)"),
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from tests._save.loaders.mocks import MockLoader

                    with persistent_cache(
                        name="cache",
                        _loader=MockLoader(
                            data={"set_state": 7, "a": 9},
                            stateful_refs={"set_state"},
                        )
                    ) as cache:
                        # Ensure the block is never hit
                        raise Exception()
                        a = 1
                        set_state(1)
                    """
                ),
            ]
        )

        assert not k.stderr.messages

        assert k.globals["a"] == 9
        assert k.globals["state"]() == 7


class TestCacheDecorator:
    async def test_basic_cache_api(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.loaders import MemoryLoader

                    @MemoryLoader.cache
                    def fib(n):
                        if n <= 1:
                            return n
                        return fib(n - 1) + fib(n - 2)

                    a = fib(5)
                    b = fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages
        assert k.globals["fib"].hits == 9

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55

    async def test_basic_cache_api_with_arg(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.loaders import MemoryLoader

                    @MemoryLoader.cache(max_size=2)
                    def fib(n):
                        if n <= 1:
                            return n
                        return fib(n - 1) + fib(n - 2)

                    a = fib(5)
                    b = fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages
        assert k.globals["fib"].hits == 14

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55

    async def test_basic_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def fib(n):
                        if n <= 1:
                            return n
                        return fib(n - 1) + fib(n - 2)

                    a = fib(5)
                    b = fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages
        assert k.globals["fib"].hits == 9

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55

    async def test_lru_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import lru_cache

                    @lru_cache(maxsize=2)
                    def fib(n):
                        if n <= 1:
                            return n
                        return fib(n - 1) + fib(n - 2)

                    a = fib(5)
                    b = fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        # More hits with a smaller cache, because it needs to check the cache
        # more.
        assert k.globals["fib"].hits == 14

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55

    async def test_lru_cache_default(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import lru_cache

                    @lru_cache
                    def fib(n):
                        if n <= 1:
                            return n
                        return fib(n - 1) + fib(n - 2)

                    a = fib(260)
                    b = fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages
        # More hits with a smaller cache, because it needs to check the cache
        # more. Has 256 entries by default, normal cache hits just 259 times.
        assert k.globals["fib"].hits == 266

        # A little ridiculous, but still low compute.
        assert (
            k.globals["a"]
            == 971183874599339129547649988289594072811608739584170445
        )
        assert k.globals["b"] == 55

    async def test_persistent_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from marimo._save.loaders import MemoryLoader

                    @persistent_cache(_loader=MemoryLoader)
                    def fib(n):
                        if n <= 1:
                            return n
                        return fib(n - 1) + fib(n - 2)

                    a = fib(5)
                    b = fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages
        assert k.globals["fib"].hits == 9

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55

    async def test_cross_cell_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("""from marimo._save.save import cache"""),
                exec_req.get(
                    """
                    @cache
                    def fib(n):
                        if n <= 1:
                            return n
                        return fib(n - 1) + fib(n - 2)
                """
                ),
                exec_req.get("""a=fib(5)"""),
                exec_req.get("""b=fib(10); a"""),
            ]
        )

        assert not k.stderr.messages
        assert k.globals["fib"].hits == 9

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55

    async def test_cross_cell_cache_with_external(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("""from marimo._save.save import cache"""),
                exec_req.get("""external = 0"""),
                exec_req.get(
                    """
                    @cache
                    def fib(n):
                        if n <= 1:
                            return n + external
                        return fib(n - 1) + fib(n - 2)
                """
                ),
                exec_req.get("""a = fib(5)"""),
                exec_req.get("""b = fib(10); a"""),
            ]
        )

        assert not k.stderr.messages

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55
        assert k.globals["fib"].hits == 9

    async def test_cross_cell_cache_with_external_state(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache
                    from marimo._runtime.state import state
                    """
                ),
                exec_req.get("""external, setter = state(0)"""),
                exec_req.get(
                    """
                    @cache
                    def fib(n):
                        if n <= 1:
                            return n + external()
                        return fib(n - 1) + fib(n - 2)
                    """
                ),
                exec_req.get("""impure = []"""),
                exec_req.get("""a = fib(5)"""),
                exec_req.get("""b = fib(10); a"""),
                exec_req.get(
                    """
                    c = a + b
                    if len(impure) == 0:
                       setter(1)
                    elif len(impure) == 1:
                       setter(0)
                    impure.append(c)
                    """
                ),
            ]
        )

        assert not k.stderr.messages

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55
        assert k.globals["impure"] == [60, 157, 60]
        # Cache hit value may be flaky depending on when state is evicted from
        # the registry. The actual cache hit is less important than caching
        # occurring in the first place.
        # NB. 20 = 2 * 9 + 2
        if k.globals["fib"].hits in (9, 18):
            warnings.warn(
                "Known flaky edge case for cache with state dep.", stacklevel=1
            )
        else:
            assert k.globals["fib"].hits == 20

    async def test_cross_cell_cache_with_external_ui(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache
                    from marimo._runtime.state import state
                    import marimo as mo
                    """
                ),
                exec_req.get("slider = mo.ui.slider(0, 1)"),
                exec_req.get("""external, setter = state("a")"""),
                exec_req.get(
                    """
                    external # To force rerun

                    @cache
                    def fib(n):
                        if n <= 1:
                            return n + slider.value
                        return fib(n - 1) + fib(n - 2)
                    """
                ),
                exec_req.get("""impure = []"""),
                exec_req.get("""a = fib(5)"""),
                exec_req.get("""b = fib(10); a"""),
                exec_req.get(
                    """
                    c = a + b
                    if len(impure) == 0:
                       setter("b")
                       slider._update(1)
                    elif len(impure) == 1:
                       setter("c")
                       slider._update(0)
                    impure.append(c)
                    """
                ),
            ]
        )

        assert not k.stderr.messages

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55
        assert k.globals["impure"] == [60, 157, 60]

        # 2 * 9 + 2
        if k.globals["fib"].hits in (9, 18):
            warnings.warn("Known flaky edge case for cache.", stacklevel=1)
        else:
            assert k.globals["fib"].hits == 20

    async def test_rerun_update(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("""from marimo._save.save import cache"""),
                exec_req.get(
                    """
                    from marimo._runtime.state import state
                    """
                ),
                exec_req.get("""max_size, setter = state(-1)"""),
                exec_req.get(
                    """from marimo._save.loaders import MemoryLoader"""
                ),
                exec_req.get("""impure = []"""),
                exec_req.get("""external = 0;c={}"""),
                exec_req.get_with_id(
                    cell_id="0",
                    code="""
                    @cache(loader=MemoryLoader.partial(max_size=max_size()))
                    def fib(n):
                        if n <= 1:
                            return n + external
                        return fib(n - 1) + fib(n - 2)
                    fib(5)
                """,
                ),
                exec_req.get("""a = fib(5)"""),
                exec_req.get("""b = fib(10); a; impure.append(b)"""),
                exec_req.get(
                    """
                if len(impure) == 1:
                    setter(256)
                    b
                """
                ),
            ]
        )
        assert not k.stderr.messages, k.stderr
        assert not k.stdout.messages, k.stdout
        # Throw a warning for flake edge case where cache is evicted earlier
        # than expected.
        if k.globals["fib"].hits in (10,):
            warnings.warn(
                "Known flaky edge case for cache rerun.", stacklevel=1
            )
        else:
            assert k.globals["fib"].hits == 10 + 3

    async def test_full_scope_utilized(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        # This is not completely obvious, but @cache needs to know what frame it
        # is on so it can get locals or globals.
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache
                    d = 0 # Check shadowing
                    """
                ),
                exec_req.get("""impure = []"""),
                exec_req.get(
                    """
                    _a = 0
                    def _b():
                        _c = 2
                        @cache
                        def d():
                            return _a + _c
                        return d
                    _e = _b()
                    impure.append([_e, _e()])
                    """
                ),
                exec_req.get(
                    repeated := """
                    _a = 0
                    def _b():
                        _c = 1
                        @cache
                        def d():
                            return _a + _c
                        return d
                    _e = _b()
                    impure.append([_e, _e()])
                    """
                ),
                exec_req.get(repeated),
            ]
        )

        assert not k.stderr.messages, k.stderr

        assert len(k.globals["impure"]) == 3
        assert {
            k.globals["impure"][0][1],
            k.globals["impure"][1][1],
            k.globals["impure"][2][1],
        } == {2, 1}

        # Same name, but should be under different entries
        assert (
            k.globals["impure"][0][0].loader
            is not k.globals["impure"][1][0].loader
        )

        assert (
            len(
                {
                    *k.globals["impure"][0][0].loader._cache.keys(),
                    *k.globals["impure"][1][0].loader._cache.keys(),
                    *k.globals["impure"][2][0].loader._cache.keys(),
                }
            )
            == 2
        )

        # No cache hits
        assert {
            k.globals["impure"][0][0].hits,
            k.globals["impure"][1][0].hits,
            k.globals["impure"][2][0].hits,
        } == {0}

    async def test_full_scope_utilized_lru_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import lru_cache
                    d = 0 # Check shadowing
                    """
                ),
                exec_req.get("""impure = []"""),
                exec_req.get(
                    """
                    _a = 0
                    def _b():
                        _c = 2
                        @lru_cache
                        def d():
                            return _a + _c
                        return d
                    _e = _b()
                    impure.append([_e, _e()])
                    """
                ),
                exec_req.get(
                    repeated := """
                    _a = 0
                    def _b():
                        _c = 1
                        @lru_cache
                        def d():
                            return _a + _c
                        return d
                    _e = _b()
                    impure.append([_e, _e()])
                    """
                ),
                exec_req.get(repeated),
            ]
        )

        assert not k.stderr.messages, k.stderr

        assert len(k.globals["impure"]) == 3
        assert {
            k.globals["impure"][0][1],
            k.globals["impure"][1][1],
            k.globals["impure"][2][1],
        } == {2, 1}

        # Same name, but should be under different entries
        assert (
            k.globals["impure"][0][0].loader
            is not k.globals["impure"][1][0].loader
        )

        assert (
            len(
                {
                    *k.globals["impure"][0][0].loader._cache.keys(),
                    *k.globals["impure"][1][0].loader._cache.keys(),
                    *k.globals["impure"][2][0].loader._cache.keys(),
                }
            )
            == 2
        )

        # No cache hits
        assert {
            k.globals["impure"][0][0].hits,
            k.globals["impure"][1][0].hits,
            k.globals["impure"][2][0].hits,
        } == {0}

    @staticmethod
    def test_object_execution_hash(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __():
            class Namespace: ...

            ns = Namespace()
            ns.x = 0
            return Namespace, ns

        @app.cell
        def __(mo, ns):
            @mo.cache
            def f():
                return ns

            return (f,)

        @app.cell
        def __(f):
            f()
            assert f.hits == 0
            assert f.base_block.execution_refs == {"ns"}
            return

    @staticmethod
    def test_execution_hash_same_block(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            class Namespace: ...

            ns = Namespace()
            ns.x = 0

            @mo.cache
            def f():
                return ns.x

            return (
                ns,
                f,
            )

        @app.cell
        def __(f, ns):
            assert f() == 0
            ns.x = 1
            assert f() == 1
            assert f.hits == 0
            assert f() == 1
            assert f.hits == 1
            assert f.base_block.context_refs == {"ns"}, (
                f.base_block.context_refs,
                f.base_block.execution_refs,
                f.base_block.content_refs,
            )
            assert f.base_block.context_refs == {"ns"}, (
                f.base_block.context_refs
            )
            return

    @staticmethod
    def test_execution_hash_diff_block(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __():
            import weakref

            class Namespace: ...

            ns = Namespace()
            ns.x = weakref.ref(ns)
            z = ns.x

            return (weakref, ns, z)

        @app.cell
        def __(mo, ns, z):
            @mo.cache
            def f():
                return ns.x, z

            return (f,)

        @app.cell
        def __(f):
            f()
            assert f.base_block.execution_refs == {"ns", "z"}
            return

    @staticmethod
    def test_content_hash_define_after(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            @mo.cache
            def f():
                return ns.x

            class Namespace: ...

            ns = Namespace()
            ns.x = 0

            return (
                ns,
                f,
            )

        @app.cell
        def __(f, ns):
            assert f() == 0
            ns.x = 1
            assert f() == 1
            assert f.hits == 0
            assert f() == 1
            assert f.hits == 1
            assert f.base_block.execution_refs == set(), (
                f.base_block.execution_refs
            )
            assert f.base_block.missing == {"ns"}, f.base_block.missing
            return

    @staticmethod
    def test_execution_hash_same_block_fails() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __():
            import weakref

            return (weakref,)

        @app.cell
        def __(mo, weakref):
            class Namespace: ...

            ns = Namespace()
            ns.x = weakref.ref(ns)
            z = ns.x

            @mo.cache
            def f():
                return ns.x, z

            return (
                ns,
                f,
            )

        @app.cell
        def __(f):
            f()
            return

        # Cannot hash the cell of the unhashable content, so it should fail
        with pytest.raises(TypeError):
            app.run()

    @staticmethod
    def test_unused_args(app) -> None:
        @app.cell
        def __():
            import random

            import marimo as mo

            return (mo, random)

        @app.cell
        def __(mo, random):
            @mo.cache
            def g(_x):
                return random.randint(0, 1000)

            return (g,)

        @app.cell
        def __(g, random):
            random.seed(0)
            a = g("hello")
            assert g("hello") == g("hello")
            random.seed(1)
            assert a == g("hello")
            assert a != g("world")
            return

    @staticmethod
    def test_shadowed_kwargs(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            @mo.cache
            def g(value="hello"):
                return value

            return g

        @app.cell
        def __(g):
            assert g() == "hello"
            assert g(value="world") == "world"
            assert g(123) == 123
            assert g.hits == 0
            assert g(value="hello") == "hello"
            # Subjective whether this hits
            # But add to test to capture behavior.
            assert g.hits == 0
            assert g() == "hello"
            assert g.hits == 1
            return

    @staticmethod
    def test_shadowed_state(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            state, set_state = mo.state(None)

            @mo.cache
            def g(state):
                return len(state)

            v = g("123")
            return (g, v)

        @app.cell
        def __(v):
            assert v == 3
            return

    @staticmethod
    def test_shadowed_state_redefined(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            state, set_state = mo.state(None)

            @mo.cache
            def g():
                return len(state)

            state = "123"

            v = g()
            return (g, v)

        @app.cell
        def __(v):
            assert v == 3
            return

    @staticmethod
    def test_internal_shadowed(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            state0, set_state0 = mo.state(1)
            state1, set_state1 = mo.state(1)
            state2, set_state2 = mo.state(10)

            state, set_state = mo.state(100)

            @mo.cache
            def h(state):
                x = state()

                def g():
                    global state

                    def f(state):
                        return x + state()

                    return state() + f(state2)

                return g()

            assert h(state0) == 111
            assert h.hits == 0
            assert h(state1) == 111
            assert h.hits == 1

    @staticmethod
    def test_transitive_shadowed_state_passes(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            state0, set_state0 = mo.state(1)
            state1, set_state1 = mo.state(1)
            state2, set_state2 = mo.state(10)

            state, set_state = mo.state(100)

            # Example of a case where things start to get very tricky. There
            # comes a point where you might also have to capture frame levels
            # as well if you mix scope.
            #
            # This is solved by rewriting potential name collisions
            def h(state):
                return state()

            def f():
                return state() + h(state2)

            @mo.cache
            def g(state):
                return state() + f()

            assert g(state0) == 111
            assert g.hits == 0
            assert g(state1) == 111
            assert g.hits == 1

    @staticmethod
    def test_shadowed_state_mismatch(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            state1, set_state1 = mo.state(1)
            state2, set_state2 = mo.state(2)

            # Here as a var for shadowing
            state, set_state = mo.state(3)

            @mo.cache
            def g(state):
                return state()

            a = g(state1)
            b = g(state2)
            assert g.hits == 0
            A = g(state1)
            B = g(state2)
            assert g.hits == 2
            return (a, b, A, B)

        @app.cell
        def __(a, b, A, B, state, state1, state2):
            assert state1() != state2()
            assert state1() == a == A
            assert state2() == b == B
            assert state() == 3
            return

    @staticmethod
    def test_shadowed_ui(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def __(mo):
            slider = mo.ui.slider(0, 1)

            @mo.cache
            def g(slider):
                return len(slider)

            v = g("123")
            return (g, v, slider)

        @app.cell
        def __(v):
            assert v == 3
            return


class TestPersistentCache:
    async def test_pickle_context(
        self, k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get("""
                import marimo as mo
                import os
                from pathlib import Path
                pc = mo.persistent_cache
                """),
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                assert not os.path.exists(tmp_path_fixture / "basic")
                with pc("basic", save_path=tmp_path_fixture) as cache:
                    _b = 1
                assert _b == 1
                assert not cache._cache.hit
                assert cache._cache.meta["version"] == mo._save.MARIMO_CACHE_VERSION
                #assert os.path.exists(tmp_path_fixture / "basic" / f"P_{cache._cache.hash}.pickle")
                """),
                exec_req.get("""
                with pc("basic", save_path=tmp_path_fixture) as cache_2:
                    _b = 1
                assert _b == 1
                assert cache_2._cache.hit
                assert cache._cache.hash == cache_2._cache.hash
                #assert os.path.exists(tmp_path_fixture / "basic" / f"P_{cache._cache.hash}.pickle")
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr

    async def test_json_context(
        self, k: Kernel, exec_req: ExecReqProvider, tmp_path
    ) -> None:
        await k.run(
            [
                exec_req.get("""
                import marimo as mo
                import os
                from pathlib import Path
                pc = mo.persistent_cache
                """),
                exec_req.get(
                    f'tmp_path_fixture = Path("{tmp_path.as_posix()}")'
                ),
                exec_req.get("""
                assert not os.path.exists(tmp_path_fixture / "json")
                with pc("json", save_path=tmp_path_fixture, method="json") as json_cache:
                    _b = 1
                assert _b == 1
                assert not json_cache._cache.hit
                #assert os.path.exists(tmp_path_fixture / "json" / f"P_{json_cache._cache.hash}.json")
                """),
                exec_req.get("""
                with pc("json", save_path=tmp_path_fixture, method="json") as json_cache_2:
                    _b = 1
                assert _b == 1
                assert json_cache_2._cache.hit
                assert json_cache._cache.hash == json_cache_2._cache.hash
                #assert os.path.exists(tmp_path_fixture / "json" / f"P_{json_cache._cache.hash}.json")
                """),
            ]
        )
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
