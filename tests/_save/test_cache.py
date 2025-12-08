# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import sys
import textwrap
import warnings
from unittest.mock import patch

import pytest

import marimo
from marimo._ast.app import App
from marimo._plugins.ui._impl.input import dropdown
from marimo._runtime.requests import ExecutionRequest
from marimo._runtime.runtime import Kernel
from marimo._save.cache import Cache, ModuleStub, UIElementStub
from tests.conftest import ExecReqProvider, TestableModuleStub


class TestCache:
    @staticmethod
    def test_cache_basic_update() -> None:
        cache = Cache(
            defs={},
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )
        scope = {}
        ret = 1
        cache.update(scope, {"return": ret})
        assert cache.meta["return"] == ret

    @staticmethod
    def test_cache_recursive_update() -> None:
        cache = Cache(
            defs={},
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )
        scope = {}
        ret = []
        ret.append(ret)
        cache.update(scope, {"return": ret})

        stored = cache.meta["return"]
        assert isinstance(stored, list)
        assert len(stored) == 1
        assert stored[0] is stored  # Self-reference maintained

    @staticmethod
    def test_cache_scope_recursive() -> None:
        _list = []
        _list.append(_list)
        d = {}
        d["self"] = d
        scope = {
            "_list": _list,
            "_dict": d,
        }
        cache = Cache(
            defs=scope,
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )

        # Force update to trigger stubbing.
        cache.update(scope, {"return": None})
        assert "_list" in cache.defs
        assert "_dict" in cache.defs

    @staticmethod
    @patch("marimo._save._cache_module.ModuleStub", TestableModuleStub)
    def test_cache_iterable() -> None:
        scope = {
            "_tuple": (1, 2, 3, marimo),
            "_set": {1, 2, 3, marimo},
        }
        cache = Cache(
            defs=scope,
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )

        # Force update to trigger stubbing.
        cache.update(scope, {"return": None})
        assert "_tuple" in cache.defs
        assert "_set" in cache.defs
        assert isinstance(cache.defs["_tuple"][-1], ModuleStub)
        assert TestableModuleStub(marimo) in cache.defs["_set"]

        cache.restore(scope)
        assert marimo == cache.defs["_tuple"][-1]
        assert marimo in cache.defs["_set"]

    @staticmethod
    def test_cache_preserves_ref() -> None:
        _set = {1, 2, 3, marimo}
        _list = [1, 2, 3, _set]
        _dict = {"_set": _set, "_list": _list}
        scope = {
            "_list": _list,
            "_set": _set,
            "_dict": _dict,
        }
        cache = Cache(
            defs=scope,
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )

        cache.update(scope, {"return": None})
        assert "_list" in cache.defs
        assert "_dict" in cache.defs
        assert "_set" in cache.defs
        assert id(cache.defs["_set"]) == id(_set)
        assert id(cache.defs["_list"]) == id(_list)
        assert id(cache.defs["_dict"]) == id(_dict)

    @staticmethod
    def test_cache_ui_element_update() -> None:
        cache = Cache(
            defs={},
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )
        scope = {}
        ret = dropdown(options=[1, 2, 3])
        cache.update(scope, {"return": ret})

        stub = cache.meta["return"]

        assert isinstance(stub, UIElementStub)

        assert stub.load().options == ret.options
        assert stub.load().value == ret.value

    @staticmethod
    def test_cache_basic_restore() -> None:
        cache = Cache(
            defs={},
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={"return": 42},
        )
        scope = {}
        cache.restore(scope)
        assert cache.meta["return"] == 42

    @staticmethod
    def test_cache_recursive_restore() -> None:
        # Create a self-referential list
        ret = []
        ret.append(ret)

        cache = Cache(
            defs={},
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={"return": ret},
        )
        scope = {}
        cache.restore(scope)

        # After restoration, should maintain the self-reference
        restored = cache.meta["return"]
        assert isinstance(restored, list)
        assert len(restored) == 1
        assert restored[0] is restored  # Self-reference maintained

    @staticmethod
    def test_cache_ui_element_restore() -> None:
        # Create a UIElement and convert it to a stub
        original_dropdown = dropdown(options=[1, 2, 3])
        stub = UIElementStub(original_dropdown)

        cache = Cache(
            defs={},
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={"return": stub},
        )
        scope = {}
        cache.restore(scope)

        # After restoration, should have a new UIElement instance with same properties
        restored = cache.meta["return"]
        assert isinstance(restored, type(original_dropdown))
        assert restored is not original_dropdown  # Different instance
        assert restored.options == original_dropdown.options
        assert restored.value == original_dropdown.value

    @staticmethod
    def test_cache_nested_ui_element_restore() -> None:
        # Create nested structure with UIElements
        slider = dropdown(options=["a", "b", "c"])
        button = dropdown(options=[1, 2, 3])
        nested = {
            "controls": [slider, button],
            "primary": slider,
            "secondary": button,
        }

        # Convert to stubs
        slider_stub = UIElementStub(slider)
        button_stub = UIElementStub(button)
        nested_with_stubs = {
            "controls": [slider_stub, button_stub],
            "primary": slider_stub,
            "secondary": button_stub,
        }

        cache = Cache(
            defs={},
            hash="123",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={"return": nested_with_stubs},
        )
        scope = {}
        cache.restore(scope)

        # After restoration, should have new UIElement instances but preserve structure
        restored = cache.meta["return"]
        assert isinstance(restored, dict)
        assert len(restored["controls"]) == 2

        # Should be same instances within the structure (shared references preserved)
        assert restored["primary"] is restored["controls"][0]
        assert restored["secondary"] is restored["controls"][1]

        # But different from originals
        assert restored["primary"] is not slider
        assert restored["secondary"] is not button

        # Properties should match
        assert restored["primary"].options == slider.options
        assert restored["secondary"].options == button.options


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
            assert cache.loader._saved
            assert not cache.loader._loaded
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
            assert not cache.loader._saved
            assert cache.loader._loaded
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
            assert not cache.loader._saved
            assert cache.loader._loaded
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
            assert not cache.loader._saved
            assert cache.loader._loaded
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
                    name="one",
                    _loader=MockLoader(data={"X": 7, "Y": 8}, strict=True)
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

    async def test_cache_module_hit(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                import marimo as mod
                from marimo._save.save import persistent_cache
                from tests._save.loaders.mocks import MockLoader

                def my_func_2():
                    return 2

                with persistent_cache(
                    name="one",
                    _loader=MockLoader(data={"mo": mod}, strict=True),
                ) as cache:
                    import numpy as mo
                """
                    ),
                ),
            ]
        )
        assert not k.stderr.messages, k.stderr
        assert not k.stdout.messages, k.stdout
        assert k.globals["mo"].__version__ == marimo.__version__

    async def test_cache_module_miss(self, any_kernel: Kernel) -> None:
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
                    import marimo as mo
                """
                    ),
                ),
            ]
        )
        # No warning messages.
        assert k.errors == {}
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        assert k.globals["mo"].__version__ == marimo.__version__

    async def test_cache_function_hit(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                from marimo._save.save import persistent_cache
                from tests._save.loaders.mocks import MockLoader

                def my_func_2():
                    return 2

                loader = MockLoader(data={"my_func": my_func_2}, strict=True)
                with persistent_cache(name="one", _loader=loader) as cache:
                    def my_func():
                        return 1
                """
                    ),
                ),
            ]
        )
        assert "cache" in k.globals
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, (k.stderr, k.stdout)
        assert k.globals["my_func"]() == 2

    async def test_cache_function_miss(self, any_kernel: Kernel) -> None:
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
                    name="one", _loader=MockLoader(),
                ) as cache:
                    def my_func():
                        return 1
                """
                    ),
                ),
            ]
        )
        # No warning messages.
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        assert k.globals["my_func"]() == 1

    async def test_cache_ui_hit(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                import marimo as mo
                from marimo._save.save import persistent_cache
                from tests._save.loaders.mocks import MockLoader
                loaded_slider = mo.ui.slider(20, 30)

                with persistent_cache(
                    name="one",
                    _loader=MockLoader(data={"slider": loaded_slider}, strict=True),
                ) as cache:
                    slider = mo.ui.slider(0, 1)
                """
                    ),
                ),
            ]
        )
        # No warning messages.
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        assert k.globals["slider"].value == 20

    async def test_cache_ui_miss(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                import marimo as mo
                from marimo._save.save import persistent_cache
                from tests._save.loaders.mocks import MockLoader

                with persistent_cache(
                    name="one", _loader=MockLoader()
                ) as cache:
                    slider = mo.ui.slider(0, 1)
                """
                    ),
                ),
            ]
        )
        # No warning messages.
        assert not k.stdout.messages, k.stdout
        assert not k.stderr.messages, k.stderr
        assert k.globals["slider"].value == 0

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

    async def test_cache_decorator_with_kwargs(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def my_cached_func(*args, **kwargs):
                        return sum(args) + sum(kwargs.values())

                    # First call with specific kwargs
                    result1 = my_cached_func(1, 2, some_kw_arg=3)
                    hash1 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Second call with different kwargs - should be cache miss
                    result2 = my_cached_func(1, 2, some_kw_arg=4)
                    hash2 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Third call with same kwargs as first - should be cache hit
                    result3 = my_cached_func(1, 2, some_kw_arg=3)
                    hash3 = my_cached_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 6  # 1 + 2 + 3
        assert k.globals["result2"] == 7  # 1 + 2 + 4
        assert k.globals["result3"] == 6  # 1 + 2 + 3

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, "Cache key should change when kwargs change"
        assert hash1 == hash3, (
            "Cache key should be same for identical args/kwargs"
        )

        # Verify cache hits
        assert k.globals["my_cached_func"].hits == 1

    async def test_cache_decorator_kwargs_expansion(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def my_cached_func(*args, **kwargs):
                        return sum(args) + sum(kwargs.values())

                    # Test with kwargs expansion
                    _kw = {"some_kw_arg": 1}
                    result1 = my_cached_func(1, 2, **_kw)
                    hash1 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with different kwargs expansion
                    _kw = {"some_kw_arg": 2}
                    result2 = my_cached_func(1, 2, **_kw)
                    hash2 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with same kwargs expansion - should hit cache
                    _kw = {"some_kw_arg": 1}
                    result3 = my_cached_func(1, 2, **_kw)
                    hash3 = my_cached_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 4  # 1 + 2 + 1
        assert k.globals["result2"] == 5  # 1 + 2 + 2
        assert k.globals["result3"] == 4  # 1 + 2 + 1

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, (
            "Cache key should change when kwargs expansion changes"
        )
        assert hash1 == hash3, (
            "Cache key should be same for identical kwargs expansion"
        )

        # Verify cache hits
        assert k.globals["my_cached_func"].hits == 1

    async def test_cache_decorator_varargs(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def my_cached_func(*args, **kwargs):
                        return sum(args) + sum(kwargs.values())

                    # Test with different varargs
                    result1 = my_cached_func(1, 2, 3)
                    hash1 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with different varargs - should be cache miss
                    result2 = my_cached_func(1, 2, 4)
                    hash2 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with same varargs - should hit cache
                    result3 = my_cached_func(1, 2, 3)
                    hash3 = my_cached_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 6  # 1 + 2 + 3
        assert k.globals["result2"] == 7  # 1 + 2 + 4
        assert k.globals["result3"] == 6  # 1 + 2 + 3

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, "Cache key should change when varargs change"
        assert hash1 == hash3, "Cache key should be same for identical varargs"

        # Verify cache hits
        assert k.globals["my_cached_func"].hits == 1

    async def test_cache_decorator_varargs_expansion(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def my_cached_func(*args, **kwargs):
                        return sum(args) + sum(kwargs.values())

                    # Test with varargs expansion
                    _args = [1, 2, 3]
                    result1 = my_cached_func(*_args)
                    hash1 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with different varargs expansion
                    _args = [1, 2, 4]
                    result2 = my_cached_func(*_args)
                    hash2 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with same varargs expansion - should hit cache
                    _args = [1, 2, 3]
                    result3 = my_cached_func(*_args)
                    hash3 = my_cached_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 6  # 1 + 2 + 3
        assert k.globals["result2"] == 7  # 1 + 2 + 4
        assert k.globals["result3"] == 6  # 1 + 2 + 3

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, (
            "Cache key should change when varargs expansion changes"
        )
        assert hash1 == hash3, (
            "Cache key should be same for identical varargs expansion"
        )

        # Verify cache hits
        assert k.globals["my_cached_func"].hits == 1

    async def test_cache_decorator_varargs_count(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def my_cached_func(*args, **kwargs):
                        return sum(args) + sum(kwargs.values())

                    _args1 = [1, 2, 3]
                    result1 = my_cached_func(*_args1)
                    hash1 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    _args2 = [1, 2]
                    result2 = my_cached_func(*_args2)
                    hash2 = my_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    _args1 = [1, 2, 3, 4]
                    result3 = my_cached_func(*_args1)
                    hash3 = my_cached_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 6  # 1 + 2 + 3
        assert k.globals["result2"] == 3  # 1 + 2
        assert k.globals["result3"] == 10  # 1 + 2 + 3 + 4

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        # The cache key should be the same for identical values regardless of variable name
        assert len({hash1, hash2, hash3}) == 3, (
            "Cache key should be same for identical values with different variable names"
        )

        # Verify cache hits
        assert k.globals["my_cached_func"].hits == 0

    async def test_persistent_cache_decorator_mixed_signature(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        # Sanity check that the same code path is captured.
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from marimo._save.loaders import MemoryLoader

                    @persistent_cache(_loader=MemoryLoader)
                    def mixed_func(arg, *vargs, kw=None, **kwargs):
                        return arg + sum(vargs) + (kw or 0) + sum(kwargs.values())

                    # Test with mixed arguments
                    result1 = mixed_func(1, 2, 3, kw=4, extra=5)
                    hash1 = mixed_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with different mixed arguments - should be cache miss
                    result2 = mixed_func(1, 2, 3, kw=4, extra=7)
                    hash2 = mixed_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with same mixed arguments - should hit cache
                    result3 = mixed_func(1, 2, 3, kw=4, extra=5)
                    hash3 = mixed_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 15  # 1 + 2 + 3 + 4 + 5
        assert k.globals["result2"] == 17  # 1 + 2 + 3 + 4 + 7
        assert k.globals["result3"] == 15  # 1 + 2 + 3 + 4 + 5

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, "Cache key should change when kwargs change"
        assert hash1 == hash3, (
            "Cache key should be same for identical mixed arguments"
        )

        # Verify cache hits
        assert k.globals["mixed_func"].hits == 1

    async def test_cache_decorator_mixed_signature(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def mixed_func(arg, *vargs, kw=None, **kwargs):
                        return arg + sum(vargs) + (kw or 0) + sum(kwargs.values())

                    # Test with mixed arguments
                    result1 = mixed_func(1, 2, 3, kw=4, extra=5)
                    hash1 = mixed_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with different mixed arguments - should be cache miss
                    result2 = mixed_func(1, 2, 3, kw=4, extra=7)
                    hash2 = mixed_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with same mixed arguments - should hit cache
                    result3 = mixed_func(1, 2, 3, kw=4, extra=5)
                    hash3 = mixed_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 15  # 1 + 2 + 3 + 4 + 5
        assert k.globals["result2"] == 17  # 1 + 2 + 3 + 4 + 7
        assert k.globals["result3"] == 15  # 1 + 2 + 3 + 4 + 5

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, "Cache key should change when kwargs change"
        assert hash1 == hash3, (
            "Cache key should be same for identical mixed arguments"
        )

        # Verify cache hits
        assert k.globals["mixed_func"].hits == 1

    async def test_cache_decorator_positional_only(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    def pos_only_func(pos1, pos2, /, kw1=None, *, kwonly):
                        return pos1 + pos2 + (kw1 or 0) + kwonly

                    # Test with positional-only arguments
                    result1 = pos_only_func(1, 2, kw1=3, kwonly=4)
                    hash1 = pos_only_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with different positional arguments - should be cache miss
                    result2 = pos_only_func(1, 3, kw1=3, kwonly=4)
                    hash2 = pos_only_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Test with same arguments - should hit cache
                    result3 = pos_only_func(1, 2, kw1=3, kwonly=4)
                    hash3 = pos_only_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 10  # 1 + 2 + 3 + 4
        assert k.globals["result2"] == 11  # 1 + 3 + 3 + 4
        assert k.globals["result3"] == 10  # 1 + 2 + 3 + 4

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, (
            "Cache key should change when positional arguments change"
        )
        assert hash1 == hash3, (
            "Cache key should be same for identical arguments"
        )

        # Verify cache hits
        assert k.globals["pos_only_func"].hits == 1

    async def test_cache_decorator_method_wrap(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    class MyClass:
                        def __init__(self, x):
                            self.x = x
                        @cache
                        def method(self, y):
                            return self.x + y

                    case_a = MyClass(0).method
                    case_b = MyClass(1).method
                    case_c = MyClass(1).method
                    result1 = case_a(2)
                    hash1 = case_a._last_hash
                    result2 = case_b(2)
                    hash2 = case_b._last_hash
                    result3 = case_c(2)
                    hash3 = case_c._last_hash

                    base_hash = MyClass.method._last_hash

                    obj = MyClass(0)
                    # __get__ is called in both places.
                    # Sanity check the functor returned.
                    get_method_0 = obj.method
                    get_method_1 = obj.method
                    """
                ),
            ]
        )

        assert not k.stdout.messages, k.stdout.messages
        assert not k.stderr.messages, k.stderr.messages

        # Verify results
        assert k.globals["result1"] == 2  # 0 + 2
        assert k.globals["result2"] == 3  # 1 + 2
        assert k.globals["result3"] == 3  # 1 + 2
        assert k.globals["hash1"] != k.globals["hash2"]
        assert k.globals["hash2"] == k.globals["hash3"]
        # Since self.loader is shared, the lookup dict is shared.
        assert k.globals["case_a"].hits == 1
        assert k.globals["case_b"].hits == 1
        assert k.globals["case_c"].hits == 1
        assert k.globals["base_hash"] is None

        # Not per say correct or incorrect; but known, documented behavior.
        assert k.globals["get_method_0"] != k.globals["get_method_1"]

    async def test_cache_static_decorator_method_wrap(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    class MyClass:

                        @staticmethod
                        @cache
                        def static_method(x, y):
                            return x + y


                    case_a = MyClass().static_method
                    case_b = MyClass().static_method
                    case_c = MyClass.static_method
                    result1 = case_a(1, 2)
                    hash1 = case_a._last_hash
                    result2 = case_b(2, 1)
                    hash2 = case_b._last_hash
                    result3 = case_c(1, 2)
                    hash3 = case_c._last_hash
                    base_hash = MyClass.static_method._last_hash
                    """
                ),
            ]
        )
        assert not k.stdout.messages, k.stdout.messages
        assert not k.stderr.messages, k.stderr.messages

        # Verify results
        assert k.globals["result1"] == 3
        assert k.globals["result2"] == 3
        assert k.globals["result3"] == 3
        assert k.globals["hash1"] != k.globals["hash2"]
        assert k.globals["hash1"] == k.globals["hash3"]
        assert k.globals["base_hash"] is not None

    async def test_cache_class_decorator_method_wrap(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    class MyClass:
                        @classmethod
                        @cache
                        def class_method(cls, x, y):
                            return x + y
                    case_a = MyClass().class_method
                    case_b = MyClass().class_method
                    case_c = MyClass.class_method
                    result1 = case_a(1, 2)
                    hash1 = case_a._last_hash
                    result2 = case_b(2, 1)
                    hash2 = case_b._last_hash
                    result3 = case_c(1, 2)
                    hash3 = case_c._last_hash
                    base_hash = MyClass.class_method._last_hash
                    """
                ),
            ]
        )
        assert not k.stdout.messages, k.stdout.messages
        assert not k.stderr.messages, k.stderr.messages

        # Verify results
        assert k.globals["result1"] == 3
        assert k.globals["result2"] == 3
        assert k.globals["result3"] == 3
        assert k.globals["hash1"] != k.globals["hash2"]
        assert k.globals["hash1"] == k.globals["hash3"]
        assert k.globals["case_c"]._last_hash is not None

        # NB. base_hash has different behavior than the others on python 3.13+
        # 3.13 has base_hash == hash1, while <3.13 has base_hash != None
        if sys.version_info >= (3, 13):
            assert k.globals["base_hash"] == k.globals["hash1"]
        else:
            assert k.globals["base_hash"] is None

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
        def _():
            import marimo as mo

            return (mo,)

        @app.cell
        def _():
            import weakref

            return (weakref,)

        @app.cell
        def _(mo, weakref):
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
        def _(f):
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

    @staticmethod
    def test_cache_with_mutation_after_def(app) -> None:
        @app.cell
        def __():
            import marimo as mo

            return (mo,)

        @app.cell
        def _(mo):
            arr = [1, 2, 3]

            @mo.cache
            def g():
                return len(arr)

            assert g() == 3
            arr.append(4)  # Mutation after definition
            assert g() == 4
            arr = [1, 2]  # Mutation after definition
            assert g() == 2
            return (g, arr)

    @staticmethod
    def test_shadowed_cell_variable_as_param(app) -> None:
        """Test that a cell variable passed to a function with same-named parameter works.

        This is a minimized version of git_arch.py that reproduces the bug.
        The bug manifests as KeyError: 'extensions' because the scope has
        '*extensions' (with ARG_PREFIX) but the hash lookup uses 'extensions'.
        """

        @app.cell
        def _():
            import marimo as mo

            return (mo,)

        @app.cell
        def _():
            from datetime import datetime

            return (datetime,)

        @app.cell
        def _(datetime, mo):
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def get_tracked_files(
                repo_path: str,
                commit_hash: str,
                extensions: list[str] | None = None,
            ) -> list[str]:
                return ["file1.py", "file2.py"]

            @mo.persistent_cache()
            def sample_commits(
                commits: list[tuple[str, datetime]], n_samples: int
            ) -> list[tuple[str, datetime]]:
                return commits[:n_samples]

            @mo.persistent_cache()
            def analyze_single_commit(
                repo_path: str,
                commit_hash: str,
                commit_date: datetime,
                extensions: list[str] | None,
                file_workers: int = 4,
            ) -> list[tuple[datetime, int]]:
                files = get_tracked_files(repo_path, commit_hash, extensions)
                return [(commit_date, len(files))]

            @mo.persistent_cache()
            def collect_blame_data(
                repo_path: str,
                sampled_commits: list[tuple[str, datetime]],
                extensions: list[str] | None,
                progress_bar=None,
                max_workers: int = 8,
            ) -> list[tuple[datetime, int]]:
                raw_data = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(
                            analyze_single_commit,
                            str(repo_path),
                            h,
                            d,
                            extensions,
                        ): (h, d)
                        for h, d in sampled_commits
                    }
                    for future in as_completed(futures):
                        raw_data.extend(future.result())
                return raw_data

            return collect_blame_data, sample_commits

        @app.cell
        def _(datetime, sample_commits):
            # Create more commits to force parallel execution
            all_commits = [(f"commit{i}", datetime.now()) for i in range(10)]
            sampled = sample_commits(all_commits, 10)
            extensions = [".py", ".js"]
            repo_path = "/tmp/test"
            return extensions, sampled, repo_path

        @app.cell
        def _(collect_blame_data, extensions, repo_path, sampled):
            result = collect_blame_data(repo_path, sampled, extensions)
            assert len(result) == 10
            return

    @staticmethod
    def test_shadowed_cell_variable_as_typed_param(app) -> None:
        """Test shadowing with type-annotated parameters (git_arch.py pattern).

        This reproduces the exact pattern from git_arch.py:
        - Cell creates `extensions` variable (list[str] | None)
        - @mo.cache function has typed `extensions: list[str] | None`
        - Same object passed as argument

        The bug manifests as KeyError: 'extensions' because the scope has
        '*extensions' (with ARG_PREFIX) but the hash lookup uses 'extensions'.
        """

        @app.cell
        def __():
            from typing import List, Optional

            import marimo as mo

            return mo, list, Optional

        # Cell that defines `extensions` as a cell variable (mimics git_arch.py)
        @app.cell
        def __(List, Optional):
            extensions_str = ".py,.js,.ts"
            extensions: Optional[List[str]] = (
                [ext.strip() for ext in extensions_str.split(",")]
                if extensions_str
                else None
            )
            return (extensions,)

        # Cell with cached function that has typed parameter with same name
        @app.cell
        def __(mo, extensions, List, Optional):
            @mo.cache
            def analyze_files(
                extensions: Optional[List[str]],
            ) -> int:
                if extensions is None:
                    return 0
                return len(extensions)

            return (analyze_files,)

        @app.cell
        def __(analyze_files, extensions):
            # Call with the cell variable (same name as param)
            result1 = analyze_files(extensions)

            # Call with different value
            result2 = analyze_files([".md"])

            # Call with None
            result3 = analyze_files(None)

            # Call again with original
            result4 = analyze_files(extensions)

            assert result1 == 3, f"Expected 3, got {result1}"
            assert result2 == 1, f"Expected 1, got {result2}"
            assert result3 == 0, f"Expected 0, got {result3}"
            assert result4 == 3, f"Expected 3, got {result4}"

            # Should have one cache hit (result4 reusing result1)
            assert analyze_files.hits == 1, (
                f"Expected 1 hit, got {analyze_files.hits}"
            )
            return

    @staticmethod
    def test_shadowed_cell_variable_as_param_persistent(app) -> None:
        """Test persistent_cache with cell variable passed as same-named parameter.

        This is the exact pattern from git_arch.py where:
        - Cell creates `extensions` variable
        - @mo.persistent_cache function has `extensions` parameter
        - Same object is passed as argument

        The cache should correctly hash based on the parameter value.
        """

        @app.cell
        def __():
            import marimo as mo
            from tests._save.loaders.mocks import MockLoader

            return mo, MockLoader

        # Cell that defines `extensions` as a cell variable
        @app.cell
        def __():
            extensions = [".py", ".js", ".ts"]
            return (extensions,)

        # Cell that defines a function with `extensions` parameter (same name)
        @app.cell
        def __(mo, MockLoader, extensions):
            @mo.persistent_cache(_loader=MockLoader)
            def analyze_files(extensions):
                return sum(len(ext) for ext in extensions)

            return (analyze_files,)

        @app.cell
        def __(analyze_files, extensions):
            # Call with the cell variable
            result1 = analyze_files(extensions)
            hash1 = analyze_files._last_hash

            # Call with a different list
            result2 = analyze_files([".md"])
            hash2 = analyze_files._last_hash

            # Call again with original to verify correct caching
            result3 = analyze_files(extensions)
            hash3 = analyze_files._last_hash

            # Verify results
            assert result1 == 9, (
                f"Expected 9 (.py=3 + .js=3 + .ts=3), got {result1}"
            )
            assert result2 == 3, f"Expected 3 (.md=3), got {result2}"
            assert result3 == 9, f"Expected 9, got {result3}"

            # Hash should be different for different inputs
            assert hash1 != hash2, (
                "Hash should differ for different extensions"
            )
            # Hash should be same for same inputs
            assert hash1 == hash3, (
                "Hash should be same for identical extensions"
            )

            # Should have one cache hit
            assert analyze_files.hits == 1, (
                f"Expected 1 hit, got {analyze_files.hits}"
            )
            return

    @staticmethod
    def test_shadowed_ui_variable_threadpool() -> None:
        """Test shadow error with UI-derived variable and ThreadPoolExecutor.

        This reproduces the bug from git_arch.py where:
        - `extensions` is derived from a UI element (mo.ui.text)
        - A cached function takes `extensions` as parameter
        - That cached function is called via ThreadPoolExecutor.submit()
        - A helper function also takes `extensions` as parameter

        The bug causes KeyError: 'extensions' at hash.py:618 because
        scope has '*extensions' (with ARG_PREFIX) but hash lookup uses 'extensions'.
        """
        app = marimo.App()

        @app.cell
        def _():
            import marimo as mo

            return (mo,)

        @app.cell
        def _():
            import subprocess
            from datetime import datetime

            return datetime, subprocess

        @app.cell
        def _(mo):
            file_extensions_input = mo.ui.text(value=".py,.md")
            file_extensions_input
            return (file_extensions_input,)

        @app.cell
        def _(datetime, mo, subprocess):
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def run_git_command(cmd: list[str], repo_path: str) -> str:
                """Stubbed helper."""
                return "a.py\nb.md\nc.txt"

            def get_tracked_files(
                repo_path: str,
                commit_hash: str,
                extensions: list[str] | None = None,
            ) -> list[str]:
                output = run_git_command(
                    ["git", "ls-tree", "-r", "--name-only", commit_hash],
                    repo_path,
                )
                files = output.strip().split("\n")
                if extensions:
                    files = [
                        f
                        for f in files
                        if any(f.endswith(ext) for ext in extensions)
                    ]
                return [f for f in files if f]

            @mo.persistent_cache()
            def analyze_single_commit(
                repo_path: str,
                commit_hash: str,
                commit_date: datetime,
                extensions: list[str] | None,
            ) -> list[tuple[datetime, int]]:
                files = get_tracked_files(repo_path, commit_hash, extensions)
                return [(commit_date, len(files))]

            @mo.persistent_cache()
            def collect_blame_data(
                repo_path: str,
                sampled_commits: list[tuple[str, datetime]],
                extensions: list[str] | None,
            ) -> list[tuple[datetime, int]]:
                raw_data = []
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {
                        executor.submit(
                            analyze_single_commit,
                            str(repo_path),
                            h,
                            d,
                            extensions,
                        ): (h, d)
                        for h, d in sampled_commits
                    }
                    for future in as_completed(futures):
                        raw_data.extend(future.result())
                return raw_data

            return (collect_blame_data,)

        @app.cell
        def _(datetime, file_extensions_input):
            repo_path = "/tmp"
            extensions_str = file_extensions_input.value.strip()
            extensions = (
                [ext.strip() for ext in extensions_str.split(",")]
                if extensions_str
                else None
            )
            sampled = [("abc123", datetime.now())]
            return extensions, repo_path, sampled

        @app.cell
        def _(collect_blame_data, extensions, repo_path, sampled):
            raw_data = collect_blame_data(repo_path, sampled, extensions)
            return (raw_data,)

        app.run()


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


class TestCacheStatistics:
    """Tests for cache statistics API (cache_info(), cache_clear())"""

    async def test_cache_info_and_clear(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Verify cache_info() and cache_clear() work correctly."""
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache, lru_cache

                    @cache
                    def func(x):
                        return x * 2

                    @lru_cache(maxsize=2)
                    def lru_func(x):
                        return x * 3

                    # Test basic cache_info
                    info0 = func.cache_info()
                    func(1)
                    func(1)  # hit
                    func(2)  # miss
                    info1 = func.cache_info()

                    # Test lru_cache maxsize
                    lru_info = lru_func.cache_info()

                    # Test cache_clear
                    func.cache_clear()
                    info2 = func.cache_info()
                    """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr

        # Initial state
        info0 = k.globals["info0"]
        assert info0.hits == 0
        assert info0.misses == 0
        assert info0.maxsize is None
        assert info0.currsize == 0
        assert info0.time_saved == 0.0

        # After calls
        info1 = k.globals["info1"]
        assert info1.hits == 1
        assert info1.misses == 2
        assert info1.currsize == 2

        # LRU maxsize
        lru_info = k.globals["lru_info"]
        assert lru_info.maxsize == 2

        # After clear
        info2 = k.globals["info2"]
        assert info2.currsize == 0

    async def test_persistent_cache_clear(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Verify cache_clear() works with persistent cache decorator."""
        await k.run(
            [
                exec_req.get("""
                    from marimo._save.loaders.memory import MemoryLoader
                    from marimo._save.save import persistent_cache

                    @persistent_cache(_loader=MemoryLoader)
                    def calc(x):
                        return x * 2

                    # First call - miss
                    r1 = calc(5)
                    info1 = calc.cache_info()

                    # Second call - hit
                    r2 = calc(5)
                    info2 = calc.cache_info()

                    # Clear
                    calc.cache_clear()
                    info3 = calc.cache_info()

                    # Call again - should be miss
                    r3 = calc(5)
                    info4 = calc.cache_info()
                    """),
            ]
        )

        assert not k.stderr.messages, k.stderr

        # Should have 1 hit before clear
        info2 = k.globals["info2"]
        assert info2.hits == 1

        # After clear: should be empty
        info3 = k.globals["info3"]
        assert info3.currsize == 0

        # After calling again: should be a miss
        info4 = k.globals["info4"]
        assert info4.misses >= 1

    async def test_cache_time_tracking(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Verify time_saved is tracked and included in cache_info()."""
        await k.run(
            [
                exec_req.get("""
                    import time
                    from marimo._save.save import cache

                    @cache
                    def slow_func(x):
                        time.sleep(0.01)  # Simulate slow operation
                        return x * 2

                    # Initial state
                    info0 = slow_func.cache_info()

                    # First call - miss (should record runtime)
                    r1 = slow_func(5)
                    info1 = slow_func.cache_info()

                    # Second call - hit (should add to time_saved)
                    r2 = slow_func(5)
                    info2 = slow_func.cache_info()

                    # Third call - another hit (should accumulate time_saved)
                    r3 = slow_func(5)
                    info3 = slow_func.cache_info()
                    """),
            ]
        )

        assert not k.stderr.messages, k.stderr

        # Initial state: no time saved yet
        info0 = k.globals["info0"]
        assert info0.time_saved == 0.0

        # After first call (miss): still no time saved
        info1 = k.globals["info1"]
        assert info1.time_saved == 0.0

        # After first hit: should have some time saved
        info2 = k.globals["info2"]
        assert info2.time_saved > 0.0
        first_saving = info2.time_saved

        # After second hit: time_saved should accumulate
        info3 = k.globals["info3"]
        assert info3.time_saved > first_saving
        assert info3.hits == 2


class TestAsyncCacheDecorator:
    """Tests for async function caching support."""

    async def test_basic_async_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test basic async function caching with @cache decorator."""
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    async def async_fib(n):
                        if n <= 1:
                            return n
                        a = await async_fib(n - 1)
                        b = await async_fib(n - 2)
                        return a + b

                    a = await async_fib(5)
                    b = await async_fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        assert k.globals["a"] == 5
        assert k.globals["b"] == 55
        # Should have cache hits like the sync version
        assert k.globals["async_fib"].hits == 9

    async def test_async_lru_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async function caching with @lru_cache decorator."""
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import lru_cache

                    @lru_cache(maxsize=2)
                    async def async_fib(n):
                        if n <= 1:
                            return n
                        a = await async_fib(n - 1)
                        b = await async_fib(n - 2)
                        return a + b

                    a = await async_fib(5)
                    b = await async_fib(10)
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        assert k.globals["a"] == 5
        assert k.globals["b"] == 55
        # Should have more hits with smaller cache
        assert k.globals["async_fib"].hits == 14

    async def test_async_persistent_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async function with @persistent_cache decorator."""
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import persistent_cache
                    from marimo._save.loaders import MemoryLoader

                    @persistent_cache(_loader=MemoryLoader)
                    async def async_compute(x):
                        await asyncio.sleep(0.001)  # Simulate async work
                        return x * 2

                    result1 = await async_compute(5)
                    result2 = await async_compute(5)  # Should hit cache
                    result3 = await async_compute(10)  # Should miss
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        assert k.globals["result1"] == 10
        assert k.globals["result2"] == 10
        assert k.globals["result3"] == 20
        assert k.globals["async_compute"].hits == 1

    async def test_async_cache_with_external_deps(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async cached function with external dependencies."""
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import cache

                    external_value = 10

                    @cache
                    async def async_add(x):
                        await asyncio.sleep(0.001)
                        return x + external_value

                    result1 = await async_add(5)
                    result2 = await async_add(5)  # Should hit cache
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        assert k.globals["result1"] == 15
        assert k.globals["result2"] == 15
        assert k.globals["async_add"].hits == 1

    async def test_async_cache_method(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async method caching."""
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import cache

                    class AsyncCalculator:
                        def __init__(self, base):
                            self.base = base

                        @cache
                        async def calculate(self, x):
                            await asyncio.sleep(0.001)
                            return self.base + x

                    calc = AsyncCalculator(10)
                    result1 = await calc.calculate(5)
                    result2 = await calc.calculate(5)  # Should hit cache
                    result3 = await calc.calculate(7)  # Should miss
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        assert k.globals["result1"] == 15
        assert k.globals["result2"] == 15
        assert k.globals["result3"] == 17

    async def test_async_cache_static_method(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async static method caching."""
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import cache

                    class AsyncMath:
                        @staticmethod
                        @cache
                        async def multiply(x, y):
                            await asyncio.sleep(0.001)
                            return x * y

                    result1 = await AsyncMath.multiply(3, 4)
                    result2 = await AsyncMath.multiply(3, 4)  # Should hit cache
                    result3 = await AsyncMath.multiply(5, 6)  # Should miss
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        assert k.globals["result1"] == 12
        assert k.globals["result2"] == 12
        assert k.globals["result3"] == 30

    async def test_async_cache_with_await_in_notebook(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async function that can be awaited directly in notebook context."""
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import cache

                    @cache
                    async def fetch_data(n):
                        await asyncio.sleep(0.001)
                        return n * 100

                    # Use direct await since marimo supports top-level await
                    result = await fetch_data(5)
                """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr
        assert k.globals["result"] == 500

    async def test_async_cache_info_and_clear(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Verify cache_info() and cache_clear() work correctly with async functions."""
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache, lru_cache

                    @cache
                    async def async_func(x):
                        return x * 2

                    @lru_cache(maxsize=2)
                    async def async_lru_func(x):
                        return x * 3

                    # Test basic cache_info
                    info0 = async_func.cache_info()
                    await async_func(1)
                    await async_func(1)  # hit
                    await async_func(2)  # miss
                    info1 = async_func.cache_info()

                    # Test lru_cache maxsize
                    lru_info = async_lru_func.cache_info()

                    # Test cache_clear
                    async_func.cache_clear()
                    info2 = async_func.cache_info()
                    """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr

        # Initial state
        info0 = k.globals["info0"]
        assert info0.hits == 0
        assert info0.misses == 0
        assert info0.maxsize is None
        assert info0.currsize == 0
        assert info0.time_saved == 0.0

        # After calls
        info1 = k.globals["info1"]
        assert info1.hits == 1
        assert info1.misses == 2
        assert info1.currsize == 2

        # LRU maxsize
        lru_info = k.globals["lru_info"]
        assert lru_info.maxsize == 2

        # After clear
        info2 = k.globals["info2"]
        assert info2.currsize == 0

    async def test_async_cache_time_tracking(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Verify time_saved is tracked correctly for async functions."""
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import cache

                    @cache
                    async def async_slow_func(x):
                        await asyncio.sleep(0.01)  # Simulate slow async operation
                        return x * 2

                    # Initial state
                    info0 = async_slow_func.cache_info()

                    # First call - miss (should record runtime)
                    r1 = await async_slow_func(5)
                    info1 = async_slow_func.cache_info()

                    # Second call - hit (should add to time_saved)
                    r2 = await async_slow_func(5)
                    info2 = async_slow_func.cache_info()

                    # Third call - another hit (should accumulate time_saved)
                    r3 = await async_slow_func(5)
                    info3 = async_slow_func.cache_info()
                    """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr

        # Initial state: no time saved yet
        info0 = k.globals["info0"]
        assert info0.time_saved == 0.0

        # After first call (miss): still no time saved
        info1 = k.globals["info1"]
        assert info1.time_saved == 0.0

        # After first hit: should have some time saved
        info2 = k.globals["info2"]
        assert info2.time_saved > 0.0
        first_saving = info2.time_saved

        # After second hit: time_saved should accumulate
        info3 = k.globals["info3"]
        assert info3.time_saved > first_saving
        assert info3.hits == 2

    async def test_async_cache_class_method(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async class method caching."""
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import cache

                    class AsyncMath:
                        @classmethod
                        @cache
                        async def compute(cls, x, y):
                            await asyncio.sleep(0.001)
                            return x + y

                    case_a = AsyncMath().compute
                    case_b = AsyncMath().compute
                    case_c = AsyncMath.compute
                    result1 = await case_a(1, 2)
                    hash1 = case_a._last_hash
                    result2 = await case_b(2, 1)
                    hash2 = case_b._last_hash
                    result3 = await case_c(1, 2)
                    hash3 = case_c._last_hash
                    base_hash = AsyncMath.compute._last_hash
                    """
                ),
            ]
        )

        assert not k.stdout.messages, k.stdout.messages
        assert not k.stderr.messages, k.stderr.messages

        # Verify results
        assert k.globals["result1"] == 3
        assert k.globals["result2"] == 3
        assert k.globals["result3"] == 3
        assert k.globals["hash1"] != k.globals["hash2"]
        assert k.globals["hash1"] == k.globals["hash3"]
        assert k.globals["case_c"]._last_hash is not None

        # NB. base_hash has different behavior than the others on python 3.13+
        # 3.13 has base_hash == hash1, while <3.13 has base_hash != None
        import sys

        if sys.version_info >= (3, 13):
            assert k.globals["base_hash"] == k.globals["hash1"]
        else:
            assert k.globals["base_hash"] is None

    async def test_async_lru_cache_default(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async lru_cache with default maxsize (256)."""
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import lru_cache

                    @lru_cache
                    async def async_fib(n):
                        if n <= 1:
                            return n
                        a = await async_fib(n - 1)
                        b = await async_fib(n - 2)
                        return a + b

                    a = await async_fib(260)
                    b = await async_fib(10)
                    """
                ),
            ]
        )

        assert not k.stderr.messages
        # More hits with a smaller cache, because it needs to check the cache
        # more. Has 256 entries by default, normal cache hits just 259 times.
        assert k.globals["async_fib"].hits == 266

        # A little ridiculous, but still low compute.
        assert (
            k.globals["a"]
            == 971183874599339129547649988289594072811608739584170445
        )
        assert k.globals["b"] == 55

    async def test_async_cross_cell_cache(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async function caching across multiple notebook cells."""
        await k.run(
            [
                exec_req.get("""from marimo._save.save import cache"""),
                exec_req.get(
                    """
                    @cache
                    async def async_fib(n):
                        if n <= 1:
                            return n
                        a = await async_fib(n - 1)
                        b = await async_fib(n - 2)
                        return a + b
                """
                ),
                exec_req.get("""a = await async_fib(5)"""),
                exec_req.get("""b = await async_fib(10); a"""),
            ]
        )

        assert not k.stderr.messages
        assert k.globals["async_fib"].hits == 9

        assert k.globals["a"] == 5
        assert k.globals["b"] == 55

    async def test_async_cache_with_external_state(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test async cached function with mo.state() dependency."""
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
                    async def async_fib(n):
                        if n <= 1:
                            return n + external()
                        a = await async_fib(n - 1)
                        b = await async_fib(n - 2)
                        return a + b
                    """
                ),
                exec_req.get("""impure = []"""),
                exec_req.get("""a = await async_fib(5)"""),
                exec_req.get("""b = await async_fib(10); a"""),
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
        if k.globals["async_fib"].hits in (9, 18):
            import warnings

            warnings.warn(
                "Known flaky edge case for async cache with state dep.",
                stacklevel=1,
            )
        else:
            assert k.globals["async_fib"].hits == 20

    async def test_async_cache_decorator_with_kwargs(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test that kwargs hashing works identically for async functions."""
        await k.run(
            [
                exec_req.get(
                    """
                    from marimo._save.save import cache

                    @cache
                    async def async_cached_func(*args, **kwargs):
                        return sum(args) + sum(kwargs.values())

                    # First call with specific kwargs
                    result1 = await async_cached_func(1, 2, some_kw_arg=3)
                    hash1 = async_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Second call with different kwargs - should be cache miss
                    result2 = await async_cached_func(1, 2, some_kw_arg=4)
                    hash2 = async_cached_func._last_hash
                    """
                ),
                exec_req.get(
                    """
                    # Third call with same kwargs as first - should be cache hit
                    result3 = await async_cached_func(1, 2, some_kw_arg=3)
                    hash3 = async_cached_func._last_hash
                    """
                ),
            ]
        )

        # Verify results
        assert k.globals["result1"] == 6  # 1 + 2 + 3
        assert k.globals["result2"] == 7  # 1 + 2 + 4
        assert k.globals["result3"] == 6  # 1 + 2 + 3

        # Verify cache keys
        hash1 = k.globals["hash1"]
        hash2 = k.globals["hash2"]
        hash3 = k.globals["hash3"]

        assert hash1 != hash2, "Cache key should change when kwargs change"
        assert hash1 == hash3, (
            "Cache key should be same for identical args/kwargs"
        )

        # Verify cache hits
        assert k.globals["async_cached_func"].hits == 1

    async def test_async_cache_concurrent_deduplication(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """Test that concurrent calls to the same async cached function are deduplicated.

        When multiple async calls are made concurrently with the same arguments,
        only one execution should occur - the rest should await the same task.
        This prevents race conditions and duplicate work.
        """
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    from marimo._save.save import cache

                    call_count = 0

                    @cache
                    async def expensive_async_compute(x):
                        global call_count
                        call_count += 1
                        await asyncio.sleep(0.1)  # Simulate expensive async work
                        return x * 2

                    # Launch 5 concurrent calls with the same argument
                    # Only one should actually execute, the rest should await that task
                    results = await asyncio.gather(
                        expensive_async_compute(42),
                        expensive_async_compute(42),
                        expensive_async_compute(42),
                        expensive_async_compute(42),
                        expensive_async_compute(42),
                    )
                    """
                ),
            ]
        )

        assert not k.stderr.messages, k.stderr

        # All results should be the same
        results = k.globals["results"]
        assert all(r == 84 for r in results), "All results should be 84"

        # The function should only have been called once (deduplication worked)
        assert k.globals["call_count"] == 1, (
            f"Expected 1 execution due to deduplication, got {k.globals['call_count']}"
        )

        # Cache hit should be 0 (first execution is a miss)
        # Note: The first call misses, subsequent concurrent calls await the same task
        assert k.globals["expensive_async_compute"].hits == 0, (
            "First execution should be a miss, deduplication doesn't count as hits"
        )
