from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Generic, Optional, TypeVar, cast

from marimo._entrypoints.ids import KnownEntryPoint

if TYPE_CHECKING:
    from importlib.metadata import EntryPoints

T = TypeVar("T")


class EntryPointRegistry(Generic[T]):
    """A registry for entry points.

    This registry allows entry points to be loaded in two ways:
    1. Through an explicit call to `.register(name, value)`
    2. By looking for Python packages that provide a setuptools entry point group

    Usage:
        registry = EntryPointRegistry[MyType]("my_entrypoint_group")
    """

    def __init__(self, entry_point_group: KnownEntryPoint) -> None:
        """Create an EntryPointRegistry for a named entry point group.

        Args:
            entry_point_group: The name of the entry point group.
        """
        self.entry_point_group: KnownEntryPoint = entry_point_group
        self._plugins: dict[str, T] = {}

    def register(self, name: str, value: T) -> None:
        """Register a plugin by name and value.

        Args:
            name: The name of the plugin.
            value: The actual plugin object to register.
        """
        self._plugins[name] = value

    def unregister(self, name: str) -> Optional[T]:
        """Unregister a plugin by name.

        Args:
            name: The name of the plugin to unregister.

        Returns:
            The plugin that was unregistered.
        """
        return self._plugins.pop(name, None)

    def names(self) -> list[str]:
        """List the names of the registered and entry points plugins.

        Returns:
            A sorted list of plugin names.
        """
        registered = list(self._plugins.keys())
        entry_points_list = get_entry_points(self.entry_point_group)
        entry_point_names = [ep.name for ep in entry_points_list]
        return sorted(set(registered + entry_point_names))

    def get(self, name: str) -> T:
        """Get a plugin by name, loading it from entry points if necessary.

        Args:
            name: The name of the plugin to get.

        Returns:
            The requested plugin.

        Raises:
            KeyError: If the plugin cannot be found.
        """
        if name in self._plugins:
            return self._plugins[name]

        entry_points_list = get_entry_points(self.entry_point_group)
        for ep in entry_points_list:
            if ep.name == name:
                value = ep.load()
                self.register(name, value)
                return cast(T, value)

        raise KeyError(
            f"No entry point named '{name}' found in group '{self.entry_point_group}'"
        )

    def get_all(self) -> list[T]:
        """Get all registered and entry point plugins.

        Returns:
            A list of all registered and entry point plugins.
        """
        return [self.get(name) for name in self.names()]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(group={self.entry_point_group!r}, registered={self.names()!r})"


def get_entry_points(group: KnownEntryPoint) -> "EntryPoints":
    ep = entry_points()
    if hasattr(ep, "select"):
        return ep.select(group=group)
    else:
        return ep.get(group, [])  # type: ignore
