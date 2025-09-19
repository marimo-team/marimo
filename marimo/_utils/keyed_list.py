from __future__ import annotations

import sys
from collections import OrderedDict, UserList
from collections.abc import Iterable
from typing import (
    Callable,
    SupportsIndex,
    TypeVar,
    cast,
    overload,
)

if sys.version_info < (3, 10):
    from typing_extensions import override
else:
    from typing import override

T = TypeVar("T")


class KeyedList(UserList[T]):
    """
    Subclass of UserList that allows for keyed access (O(1) lookup) to the list.

    I would use an OrderedDict, but we want to serialize this as a list.
    """

    def __init__(self, items: Iterable[T], to_key: Callable[[T], str]):
        """
        Initialize the KeyedList.
        """
        super().__init__()
        self._to_key: Callable[[T], str] = to_key
        self._key_to_item: OrderedDict[str, T] = OrderedDict[str, T]()

        # Add items, handling duplicate keys by keeping the last one
        for item in items:
            key = to_key(item)
            # If key already exists, remove old item from data list
            if key in self._key_to_item:
                old_item = self._key_to_item[key]
                try:
                    self.data.remove(old_item)
                except ValueError:
                    pass  # Item not in list somehow

            self._key_to_item[key] = item
            self.data.append(item)

    @overload
    def __getitem__(self, idx: SupportsIndex) -> T: ...

    @overload
    def __getitem__(self, idx: slice) -> KeyedList[T]: ...

    @override
    def __getitem__(self, idx: SupportsIndex | slice) -> T | KeyedList[T]:
        """Get item by integer index or slice."""
        result = self.data[idx]
        if isinstance(idx, slice):
            # Create a new UserList with the sliced result
            new_list = self.data[idx]
            return KeyedList[T](new_list, self._to_key)
        return cast(T, result)

    @overload
    def __setitem__(self, idx: SupportsIndex, value: T) -> None: ...

    @overload
    def __setitem__(self, idx: slice, value: Iterable[T]) -> None: ...

    @override
    def __setitem__(
        self, idx: SupportsIndex | slice, value: T | Iterable[T]
    ) -> None:
        """Set item by integer index or slice."""
        if isinstance(idx, slice):
            # Handle slice assignment
            if not isinstance(value, Iterable):
                raise TypeError("can only assign an iterable")
            value_list = list(cast(Iterable[T], value))
            # Remove old items from key mapping
            old_items = self.data[idx]
            for old_item in old_items:
                old_key = self._to_key(old_item)
                if old_key in self._key_to_item:
                    del self._key_to_item[old_key]
            # Set new items
            self.data[idx] = value_list
            # Add new items to key mapping
            for new_item in value_list:
                new_key = self._to_key(new_item)
                self._key_to_item[new_key] = new_item
        else:
            # Handle single item assignment
            old_item = self.data[idx]
            old_key = self._to_key(old_item)
            typed_value = cast(T, value)
            new_key = self._to_key(typed_value)

            # Remove old key mapping
            if old_key in self._key_to_item:
                del self._key_to_item[old_key]

            # Update data and key mapping
            self.data[idx] = typed_value
            self._key_to_item[new_key] = typed_value

    @override
    def __delitem__(self, idx: SupportsIndex | slice) -> None:
        """Delete item by integer index or slice."""
        if isinstance(idx, slice):
            # Handle slice deletion
            old_items = self.data[idx]
            for old_item in old_items:
                old_key = self._to_key(old_item)
                if old_key in self._key_to_item:
                    del self._key_to_item[old_key]
            del self.data[idx]
        else:
            # Handle single item deletion
            item = self.data[idx]
            key = self._to_key(item)

            # Remove from both data list and key mapping
            del self.data[idx]
            if key in self._key_to_item:
                del self._key_to_item[key]

    @override
    def __contains__(self, item: object) -> bool:
        """Check if item is in the list."""
        try:
            # We need to cast to T for the key function, but we know this might fail
            return self._to_key(cast(T, item)) in self._key_to_item
        except (TypeError, AttributeError):
            return False

    def get_by_key(self, key: str) -> T | None:
        """Get item by key with O(1) lookup."""
        return self._key_to_item.get(key)

    def has_key(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._key_to_item

    def remove_by_key(self, key: str) -> bool:
        """Remove item by key. Returns True if item was found and removed."""
        if key not in self._key_to_item:
            return False

        item = self._key_to_item[key]
        try:
            self.data.remove(item)
            del self._key_to_item[key]
            return True
        except ValueError:
            # Item not in data list somehow, just remove from key mapping
            del self._key_to_item[key]
            return True

    @override
    def append(self, item: T) -> None:
        """Append item to the list. If key already exists, replaces the existing item."""
        key = self._to_key(item)

        # If key already exists, remove old item
        if key in self._key_to_item:
            old_item = self._key_to_item[key]
            try:
                self.data.remove(old_item)
            except ValueError:
                pass

        # Add new item
        self.data.append(item)
        self._key_to_item[key] = item

    @override
    def insert(self, i: int, item: T) -> None:
        """Insert item at the given index."""
        key = self._to_key(item)

        # If key already exists, remove old item first
        if key in self._key_to_item:
            old_item = self._key_to_item[key]
            try:
                old_index = self.data.index(old_item)
                self.data.pop(old_index)
                # Adjust insertion index if needed
                if old_index < i:
                    i -= 1
            except ValueError:
                pass

        # Insert new item
        self.data.insert(i, item)
        self._key_to_item[key] = item
