# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, TypeGuard, TypeVar, overload

from marimo._entrypoints.ids import KnownEntryPoint
from marimo._entrypoints.registry import get_entry_points

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

T_co = TypeVar("T_co", covariant=True)


class CellView(Protocol):
    """Read-only cell data exposed to capabilities."""

    @property
    def id(self) -> str: ...

    @property
    def code(self) -> str: ...

    @property
    def definitions(self) -> frozenset[str]: ...

    @property
    def references(self) -> frozenset[str]: ...


class CellsView(Protocol):
    """Read-only access to notebook cells."""

    @overload
    def __getitem__(self, key: int) -> CellView: ...

    @overload
    def __getitem__(self, key: str) -> CellView: ...

    def __iter__(self) -> Iterator[CellView]: ...


class CapabilityContext(Protocol):
    """Read-only code-mode surface provided to capabilities."""

    @property
    def globals(self) -> Mapping[str, Any]: ...

    @property
    def cells(self) -> CellsView: ...


class Capability(Protocol[T_co]):
    """A capability provided by a `marimo.agent.capability` entry point."""

    @property
    def description(self) -> str: ...

    @property
    def instructions(self) -> str: ...

    def bind(self, context: CapabilityContext) -> T_co: ...


@dataclass(frozen=True, slots=True)
class _CellSnapshot:
    id: str
    code: str
    definitions: frozenset[str]
    references: frozenset[str]


class _CellsSnapshot:
    def __init__(self, cells: Sequence[_CellSnapshot]) -> None:
        self._cells = tuple(cells)

    @overload
    def __getitem__(self, key: int) -> _CellSnapshot: ...

    @overload
    def __getitem__(self, key: str) -> _CellSnapshot: ...

    def __getitem__(self, key: int | str) -> _CellSnapshot:
        if isinstance(key, int):
            return self._cells[key]
        for cell in self._cells:
            if cell.id == key:
                return cell
        raise KeyError(key)

    def __iter__(self) -> Iterator[_CellSnapshot]:
        return iter(self._cells)


class _CapabilityContext:
    def __init__(self, context: CapabilityContext) -> None:
        self._globals = MappingProxyType(dict(context.globals))
        self._cells = _CellsSnapshot(
            [
                _CellSnapshot(
                    id=cell.id,
                    code=cell.code,
                    definitions=frozenset(cell.definitions),
                    references=frozenset(cell.references),
                )
                for cell in context.cells
            ]
        )

    @property
    def globals(self) -> Mapping[str, Any]:
        return self._globals

    @property
    def cells(self) -> _CellsSnapshot:
        return self._cells


class _LoadedCapability:
    def __init__(self, capability: Capability[Any]) -> None:
        self._capability = capability

    @property
    def description(self) -> str:
        return self._capability.description

    @property
    def instructions(self) -> str:
        return self._capability.instructions

    def bind(self, context: CapabilityContext) -> Any:
        return self._capability.bind(_CapabilityContext(context))


def _is_capability(value: object) -> TypeGuard[Capability[Any]]:
    return (
        isinstance(getattr(value, "description", None), str)
        and isinstance(getattr(value, "instructions", None), str)
        and callable(getattr(value, "bind", None))
    )


_ENTRY_POINT_GROUP: KnownEntryPoint = "marimo.agent.capability"
_LOADED_CAPABILITIES: dict[str, _LoadedCapability] = {}


def capabilities() -> tuple[str, ...]:
    """Return installed capability names without importing them."""
    return tuple(
        sorted(
            {
                entry_point.name
                for entry_point in get_entry_points(_ENTRY_POINT_GROUP)
            }
        )
    )


def load_capability(name: str) -> _LoadedCapability:
    """Load and cache one installed capability."""
    if name in _LOADED_CAPABILITIES:
        return _LOADED_CAPABILITIES[name]

    matches = [
        entry_point
        for entry_point in get_entry_points(_ENTRY_POINT_GROUP)
        if entry_point.name == name
    ]
    if not matches:
        raise KeyError(f"Capability {name!r} is not installed")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple capabilities are registered as {name!r}")

    try:
        capability = matches[0].load()
    except Exception as exc:
        raise RuntimeError(f"Failed to import capability {name!r}") from exc

    if not _is_capability(capability):
        raise TypeError(
            f"Capability {name!r} must provide string 'description' and "
            "'instructions' attributes and a callable 'bind'"
        )

    loaded = _LoadedCapability(capability)
    _LOADED_CAPABILITIES[name] = loaded
    return loaded
