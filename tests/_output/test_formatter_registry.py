from __future__ import annotations

from dataclasses import dataclass

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatting import Formatter, FormatterRegistry


# Test classes for hierarchy testing
@dataclass
class BaseClass:
    value: str = "base"


class ChildClass(BaseClass):
    def __init__(self, value: str = "child"):
        super().__init__(value)


class GrandChildClass(ChildClass):
    def __init__(self, value: str = "grandchild"):
        super().__init__(value)


# Multiple inheritance test classes
class MixinA:
    pass


class MixinB:
    pass


class MultipleInheritanceClass(MixinA, MixinB, BaseClass):
    pass


# Test formatters
def base_formatter(obj: BaseClass) -> tuple[KnownMimeType, str]:
    return ("text/html", f"<span>Base: {obj.value}</span>")


def child_formatter(obj: ChildClass) -> tuple[KnownMimeType, str]:
    return ("text/html", f"<span>Child: {obj.value}</span>")


def mixin_a_formatter(obj: MixinA) -> tuple[KnownMimeType, str]:
    assert isinstance(obj, MixinA)
    return ("text/html", "<span>MixinA</span>")


def int_formatter(obj: int) -> tuple[KnownMimeType, str]:
    return ("text/plain", f"Integer: {obj}")


class TestFormatterRegistry:
    def test_init(self):
        """Test that FormatterRegistry initializes with empty formatters dict."""
        registry = FormatterRegistry()
        assert registry.formatters == {}
        assert registry.is_empty()

    def test_is_empty_when_empty(self):
        """Test is_empty returns True for empty registry."""
        registry = FormatterRegistry()
        assert registry.is_empty()

    def test_is_empty_when_not_empty(self):
        """Test is_empty returns False when registry has formatters."""
        registry = FormatterRegistry()
        registry.add_formatter(int, int_formatter)
        assert not registry.is_empty()

    def test_add_formatter(self):
        """Test adding a formatter to the registry."""
        registry = FormatterRegistry()
        registry.add_formatter(int, int_formatter)

        assert int in registry.formatters
        assert registry.formatters[int] == int_formatter
        assert not registry.is_empty()

    def test_add_multiple_formatters(self):
        """Test adding multiple formatters."""
        registry = FormatterRegistry()
        registry.add_formatter(int, int_formatter)
        registry.add_formatter(BaseClass, base_formatter)

        assert len(registry.formatters) == 2
        assert registry.formatters[int] == int_formatter
        assert registry.formatters[BaseClass] == base_formatter

    def test_get_formatter_direct_match(self):
        """Test getting formatter for exact type match."""
        registry = FormatterRegistry()
        registry.add_formatter(int, int_formatter)

        obj = 42
        formatter = registry.get_formatter(obj)

        assert formatter == int_formatter

    def test_get_formatter_no_match(self):
        """Test getting formatter when no match exists."""
        registry = FormatterRegistry()

        obj = "string"
        formatter = registry.get_formatter(obj)

        assert formatter is None

    def test_get_formatter_hierarchy_match(self):
        """Test getting formatter through type hierarchy (mro)."""
        registry = FormatterRegistry()
        registry.add_formatter(BaseClass, base_formatter)

        # ChildClass should get BaseClass formatter
        child_obj = ChildClass()
        formatter = registry.get_formatter(child_obj)

        assert formatter == base_formatter

    def test_get_formatter_hierarchy_caching(self):
        """Test that hierarchy lookups are cached."""
        registry = FormatterRegistry()
        registry.add_formatter(BaseClass, base_formatter)

        child_obj = ChildClass()

        # First call should find via hierarchy and cache
        assert ChildClass not in registry.formatters
        formatter = registry.get_formatter(child_obj)
        assert formatter == base_formatter

        # After first call, ChildClass should be cached
        assert ChildClass in registry.formatters
        assert registry.formatters[ChildClass] == base_formatter

        # Second call should use cached formatter
        formatter2 = registry.get_formatter(child_obj)
        assert formatter2 == base_formatter

    def test_get_formatter_multiple_hierarchy_levels(self):
        """Test formatter lookup through multiple inheritance levels."""
        registry = FormatterRegistry()
        registry.add_formatter(BaseClass, base_formatter)

        # GrandChildClass -> ChildClass -> BaseClass hierarchy
        grandchild_obj = GrandChildClass()
        formatter = registry.get_formatter(grandchild_obj)

        assert formatter == base_formatter

    def test_get_formatter_prefer_exact_match_over_hierarchy(self):
        """Test that exact type matches take precedence over hierarchy."""
        registry = FormatterRegistry()
        registry.add_formatter(BaseClass, base_formatter)
        registry.add_formatter(ChildClass, child_formatter)

        child_obj = ChildClass()
        formatter = registry.get_formatter(child_obj)

        # Should get ChildClass formatter, not BaseClass
        assert formatter == child_formatter

    def test_get_formatter_multiple_inheritance(self):
        """Test formatter lookup with multiple inheritance."""
        registry = FormatterRegistry()
        registry.add_formatter(MixinA, mixin_a_formatter)
        registry.add_formatter(BaseClass, base_formatter)

        multi_obj = MultipleInheritanceClass()
        formatter = registry.get_formatter(multi_obj)

        # Should find first match in MRO order
        # MRO: MultipleInheritanceClass, MixinA, MixinB, BaseClass, object
        assert formatter == mixin_a_formatter

    def test_get_formatter_mro_order(self):
        """Test that formatter lookup follows MRO order correctly."""
        registry = FormatterRegistry()

        # Add formatters for both parent classes
        registry.add_formatter(MixinB, lambda _: ("text/plain", "MixinB"))
        registry.add_formatter(BaseClass, base_formatter)

        multi_obj = MultipleInheritanceClass()
        formatter = registry.get_formatter(multi_obj)

        # Should find MixinB first in MRO, not BaseClass
        assert formatter is not None
        mime, data = formatter(multi_obj)
        assert mime == "text/plain"
        assert data == "MixinB"

    def test_formatter_override(self):
        """Test that adding a formatter for the same type overrides the previous one."""
        registry = FormatterRegistry()

        def first_formatter(obj: int) -> tuple[KnownMimeType, str]:
            assert isinstance(obj, int)
            return ("text/plain", "first")

        def second_formatter(obj: int) -> tuple[KnownMimeType, str]:
            assert isinstance(obj, int)
            return ("text/plain", "second")

        registry.add_formatter(int, first_formatter)
        registry.add_formatter(int, second_formatter)

        obj = 42
        formatter = registry.get_formatter(obj)

        assert formatter == second_formatter

    def test_get_formatter_with_various_builtin_types(self):
        """Test formatter registry with various built-in Python types."""
        registry = FormatterRegistry()

        def str_formatter(obj: str) -> tuple[KnownMimeType, str]:
            return ("text/plain", f"String: {obj}")

        def list_formatter(obj: list[int]) -> tuple[KnownMimeType, str]:
            return ("text/plain", f"List: {obj}")

        registry.add_formatter(str, str_formatter)
        registry.add_formatter(list, list_formatter)

        # Test string
        str_obj = "test"
        assert registry.get_formatter(str_obj) == str_formatter

        # Test list
        list_obj = [1, 2, 3]
        assert registry.get_formatter(list_obj) == list_formatter

        # Test unregistered type
        dict_obj = {"key": "value"}
        assert registry.get_formatter(dict_obj) is None

    def test_registry_isolation(self):
        """Test that different registry instances are isolated."""
        registry1 = FormatterRegistry()
        registry2 = FormatterRegistry()

        registry1.add_formatter(int, int_formatter)

        obj = 42
        assert registry1.get_formatter(obj) == int_formatter
        assert registry2.get_formatter(obj) is None
        assert registry2.is_empty()

    def test_formatter_can_handle_none_values(self):
        """Test that registry handles None values gracefully."""
        registry = FormatterRegistry()
        registry.add_formatter(int, int_formatter)

        # None should not match any formatter
        formatter = registry.get_formatter(None)
        assert formatter is None

    def test_formatter_type_annotations_preserved(self):
        """Test that type annotations work correctly with formatters."""
        registry = FormatterRegistry()

        # This should work without type errors
        formatter_func: Formatter[BaseClass] = base_formatter
        registry.add_formatter(BaseClass, formatter_func)

        obj = BaseClass()
        result_formatter = registry.get_formatter(obj)
        assert result_formatter == formatter_func

    def test_formatter_for_type(self):
        """Test that formatter for type works correctly."""
        registry = FormatterRegistry()
        registry.add_formatter(int, int_formatter)
        value = 1

        assert registry.get_formatter(value) == int_formatter
        assert registry.get_formatter(type(value)) is None
        assert registry.get_formatter(int) is None
        assert registry.get_formatter(type(int)) is None

    def test_get_formatter_handles_broken_mro(self):
        """Ensure registry gracefully handles types with broken mro()."""
        registry = FormatterRegistry()

        class Broken:
            pass

        # Shadow mro with a plain function so calling it raises a TypeError
        # because no implicit self/cls is passed for functions on classes
        def bad_mro(_self):
            del _self
            raise TypeError("broken mro")

        Broken.mro = bad_mro  # type: ignore[attr-defined]

        obj = Broken()

        # Should not raise, and should return None when MRO cannot be read
        formatter = registry.get_formatter(obj)
        assert formatter is None
