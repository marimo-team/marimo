from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from marimo._entrypoints.ids import KnownEntryPoint
from marimo._entrypoints.registry import EntryPointRegistry, get_entry_points
from marimo._runtime.executor import ExecutionConfig, Executor, get_executor


class TestEntryPointRegistry:
    @pytest.fixture
    def registry(self) -> EntryPointRegistry[str]:
        return EntryPointRegistry[str](cast(KnownEntryPoint, "plugins"))

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


class CustomExecutor(Executor):
    def execute_cell(
        self,
        cell: str,
        glbls: dict[str, str],
        graph: str,
    ) -> str:
        return f"Executed {cell} with {glbls} in {graph}"

    async def execute_cell_async(
        self,
        cell: str,
        glbls: dict[str, str],
        graph: str,
    ) -> str:
        return f"Executed {cell} with {glbls} in {graph}"


class TestExecutorEntryPoint:
    @pytest.fixture
    def registry(self) -> EntryPointRegistry[Executor]:
        reg = EntryPointRegistry[Executor]("marimo.cell.executor")
        reg.register("custom", CustomExecutor)
        return reg

    def test_get_entry_points_modern(
        self, registry: EntryPointRegistry[Executor]
    ) -> None:
        executor = get_executor(
            ExecutionConfig(is_strict=False), registry=registry
        )
        assert isinstance(executor, CustomExecutor)
