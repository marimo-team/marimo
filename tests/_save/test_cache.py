# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import textwrap

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
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            with persistent_cache(name="one", _loader=MockLoader()) as cache:
                Y = 8
                X = 7
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert cache._loader._saved
            assert not cache._loader._loaded
            return X, Y, persistent_cache

        app.run()

    @staticmethod
    def test_cache_hit() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

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

        app.run()

    @staticmethod
    def test_cache_hit_whitespace() -> None:
        app = App()
        app._anonymous_file = True

        @app.cell
        def one() -> tuple[int]:
            from marimo._save.save import persistent_cache
            from tests._save.mocks import MockLoader

            # fmt: off
            with persistent_cache(name="one", _loader=MockLoader(data={"X": 7, "Y": 8})) as cache: # noqa: E501
                Y = 9
                X = 10
            # fmt: on
            assert X == 7
            assert cache._cache.defs == {"X": 7, "Y": 8}
            assert not cache._loader._saved
            assert cache._loader._loaded
            return X, Y, persistent_cache

        app.run()


class TestAppCache:
    async def test_cache_miss(self, any_kernel: Kernel) -> None:
        k = any_kernel
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent("""
                from marimo._save.save import persistent_cache
                from tests._save.mocks import MockLoader

                with persistent_cache(name="one", _loader=MockLoader()) as cache:
                    Y = 9
                    X = 10
                Z = 3
                """),
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
                    code=textwrap.dedent("""
                from marimo._save.save import persistent_cache
                from tests._save.mocks import MockLoader

                with persistent_cache(
                    name="one", _loader=MockLoader(data={"X": 7, "Y": 8})
                ) as cache:
                    Y = 9
                    X = 10
                Z = 3
                """),
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
                    code=textwrap.dedent("""
        from marimo._save.save import persistent_cache
        from tests._save.mocks import MockLoader

        with persistent_cache(name="one", _loader=MockLoader(data={"X": 1})):
            X = 1
        Y = 2
                """),
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
                    code=textwrap.dedent("""
                from marimo._save.save import persistent_cache
                from tests._save.mocks import MockLoader

                with persistent_cache(name="one", _loader=MockLoader()):
                    # Comment

                    # whitespace
                    X = 1 # Comment
                    Y = 2
                """),
                ),
            ]
        )
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
                    from tests._save.mocks import MockLoader

                    with persistent_cache(
                        name="cache", _loader=MockLoader()
                    ) as cache:
                        set_state(a)
                    """
                ),
            ]
        )

        assert not k.globals["cache"].hit
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
                    from tests._save.mocks import MockLoader

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

        # Should be hit because of rerun
        assert len(k.globals["impure"]) == 2
        assert k.globals["impure"][0] == k.globals["impure"][1]
        assert k.globals["state"]() == 9

    async def test_set_state_invalidates(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("impure = []"),
                exec_req.get("state, set_state = mo.state(0)"),
                exec_req.get("x = state()"),
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from tests._save.mocks import MockLoader

                    with persistent_cache(
                        name="cache", _loader=MockLoader()
                    ) as cache:
                        a = x + 1

                    if len(impure) < 4:
                        impure.append(cache._cache.hash)
                        set_state(a % 3)
                    """
                ),
            ]
        )

        assert len(k.globals["impure"]) == 4
        assert len(set(k.globals["impure"])) == 3
        assert k.globals["impure"][0] == k.globals["impure"][-1]

    async def test_set_state_invalidates(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("state, set_state = mo.state(11)"),
                exec_req.get(
                    """
                    from marimo._save.save import persistent_cache
                    from tests._save.mocks import MockLoader

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
