from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest

from marimo._entrypoints.ids import KnownEntryPoint
from marimo._entrypoints.registry import EntryPointRegistry, get_entry_points
from marimo._runtime.executor import Executor

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._ast.cell import CellImpl


class TestEntryPointRegistry:
    @pytest.fixture
    def registry(self) -> EntryPointRegistry[str]:
        return EntryPointRegistry[str](
            cast(KnownEntryPoint, "marimo.test.group")
        )

    def test_register_and_get(self, registry: EntryPointRegistry[str]) -> None:
        registry.register("test", "value")
        assert registry.get("test") == "value"

    def test_unregister(self, registry: EntryPointRegistry[str]) -> None:
        registry.register("test", "value")
        assert registry.unregister("test") == "value"
        with pytest.raises(KeyError):
            registry.get("test")

    def test_names(self, registry: EntryPointRegistry[str]) -> None:
        registry.register("test1", "value1")
        registry.register("test2", "value2")
        assert set(registry.names()) == {"test1", "test2"}

    def test_get_nonexistent(self, registry: EntryPointRegistry[str]) -> None:
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_repr(self, registry: EntryPointRegistry[str]) -> None:
        registry.register("test", "value")
        assert "EntryPointRegistry" in repr(registry)
        assert "test" in repr(registry)

    def test_allowlist(self, registry: EntryPointRegistry[str]) -> None:
        with patch.dict(
            os.environ, {"MARIMO_TEST_GROUP_ALLOWLIST": "test1,test2"}
        ):
            # Allowed extension
            registry.register("test1", "value1")
            assert registry.get("test1") == "value1"

            # Not allowed extension - should be silently ignored
            registry.register("test3", "value3")
            assert "test3" not in registry.names()

            # Not allowed extension - should raise on get
            with pytest.raises(ValueError, match="not allowed"):
                registry.get("test3")

    def test_denylist(self, registry: EntryPointRegistry[str]) -> None:
        with patch.dict(
            os.environ, {"MARIMO_TEST_GROUP_DENYLIST": "test2,test3"}
        ):
            # Allowed extension
            registry.register("test1", "value1")
            assert registry.get("test1") == "value1"

            # Denied extension - should be silently ignored
            registry.register("test2", "value2")
            assert "test2" not in registry.names()

            # Denied extension - should raise on get
            with pytest.raises(ValueError, match="not allowed"):
                registry.get("test2")

    def test_allowlist_and_denylist(
        self, registry: EntryPointRegistry[str]
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "MARIMO_TEST_GROUP_ALLOWLIST": "test1,test2",
                "MARIMO_TEST_GROUP_DENYLIST": "test2,test3",
            },
        ):
            # Allowed extension
            registry.register("test1", "value1")
            assert registry.get("test1") == "value1"

            # Denied extension - should be silently ignored even if in allowlist
            registry.register("test2", "value2")
            assert "test2" not in registry.names()

            # Not in allowlist - should be silently ignored
            registry.register("test4", "value4")
            assert "test4" not in registry.names()

    def test_case_insensitive(self, registry: EntryPointRegistry[str]) -> None:
        with patch.dict(
            os.environ,
            {
                "MARIMO_TEST_GROUP_ALLOWLIST": "Test1,TEST2",
                "MARIMO_TEST_GROUP_DENYLIST": "TEST3,test4",
            },
        ):
            # Case-insensitive allowlist match
            registry.register("test1", "value1")
            registry.register("TEST2", "value2")
            assert set(registry.names()) == {"test1", "TEST2"}

            # Case-insensitive denylist match
            registry.register("Test3", "value3")
            registry.register("TEST4", "value4")
            assert "Test3" not in registry.names()
            assert "TEST4" not in registry.names()

    @patch("marimo._entrypoints.registry.entry_points")
    def test_get_entry_points_modern(
        self, mock_entry_points: MagicMock
    ) -> None:
        mock_eps = MagicMock()
        mock_eps.select.return_value = ["ep1", "ep2"]
        mock_entry_points.return_value = mock_eps

        result = get_entry_points(cast(KnownEntryPoint, "plugins"))
        assert result == ["ep1", "ep2"]
        mock_eps.select.assert_called_once_with(
            group=cast(KnownEntryPoint, "plugins")
        )

    def test_get_all(self, registry: EntryPointRegistry[str]) -> None:
        registry.register("test1", "value1")
        registry.register("test2", "value2")

        with patch(
            "marimo._entrypoints.registry.get_entry_points"
        ) as mock_get_entry_points:
            mock_get_entry_points.return_value = []
            result = registry.get_all()

        assert set(result) == {"value1", "value2"}

    @patch("marimo._entrypoints.registry.get_entry_points")
    def test_get_all_with_entry_points(
        self, mock_get_entry_points: MagicMock
    ) -> None:
        registry = EntryPointRegistry[str](cast(KnownEntryPoint, "test_group"))

        # Create mock entry points
        ep1 = MagicMock()
        ep1.name = "ep1"
        ep1.load.return_value = "ep_value1"

        ep2 = MagicMock()
        ep2.name = "ep2"
        ep2.load.return_value = "ep_value2"

        mock_get_entry_points.return_value = [ep1, ep2]

        # Register one plugin directly
        registry.register("test1", "value1")

        # Get all plugins
        result = registry.get_all()

        # Should include both registered and entry point plugins
        assert set(result) == {"value1", "ep_value1", "ep_value2"}


class CustomExecutor:
    """Protocol-conforming Executor (no ABC inheritance)."""

    name = "custom"

    def execute_cell(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
    ) -> Any:
        return f"Executed {cell} with {glbls}"

    async def execute_cell_async(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
    ) -> Any:
        return f"Executed {cell} with {glbls}"


def _custom_executor_factory() -> Executor:
    return CustomExecutor()


class TestExecutorEntryPoint:
    def test_factory_registers_and_resolves(self) -> None:
        # Registry holds factories (Callable[[], Executor]); the kernel
        # calls the factory once to get an instance.
        reg: EntryPointRegistry[Callable[[], Executor]] = EntryPointRegistry(
            "marimo.cell.executor"
        )
        reg.register("custom", _custom_executor_factory)

        factory = reg.get("custom")
        executor = factory()
        assert isinstance(executor, CustomExecutor)
        assert executor.execute_cell("c", {"x": "1"}) == (  # type: ignore[arg-type]
            "Executed c with {'x': '1'}"
        )

    def test_resolve_executor_only_loads_first_factory(self) -> None:
        """``resolve_executor`` must not import factories beyond the first.

        A broken or slow third-party plugin can't take down the kernel
        if it never gets loaded.
        """
        from marimo._runtime.executor.evaluator import (
            _EXECUTOR_REGISTRY,
            resolve_executor,
        )

        loaded: list[str] = []

        def working_factory() -> Executor:
            loaded.append("working")
            return CustomExecutor()

        def broken_factory() -> Executor:
            loaded.append("broken")
            raise RuntimeError("third-party plugin is broken")

        # Restore the registry's plugins on exit so we don't leak
        # registrations into other tests.
        before = dict(_EXECUTOR_REGISTRY._plugins)
        _EXECUTOR_REGISTRY._plugins.clear()
        try:
            _EXECUTOR_REGISTRY.register("aaa-working", working_factory)
            _EXECUTOR_REGISTRY.register("zzz-broken", broken_factory)
            executor = resolve_executor()
            assert isinstance(executor, CustomExecutor)
            assert loaded == ["working"]
        finally:
            _EXECUTOR_REGISTRY._plugins.clear()
            _EXECUTOR_REGISTRY._plugins.update(before)
