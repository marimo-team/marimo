# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass

from marimo._plugins.ui._impl.anywidget.widget_ref import (
    AnyWidgetStateSerializer,
    _replace_widget_refs,
)


@dataclass
class FakeWidget:
    """Stands in for an ipywidgets-derived AnyWidget instance."""

    model_id: str


class TestReplaceWidgetRefs:
    @staticmethod
    def test_leaves_pass_through() -> None:
        for leaf in ("text", 7, 1.5, True, b"bytes", None):
            assert _replace_widget_refs(leaf) is leaf or (
                _replace_widget_refs(leaf) == leaf
            )

    @staticmethod
    def test_widget_replaced_at_top_level() -> None:
        assert _replace_widget_refs(FakeWidget("abc")) == "anywidget:abc"

    @staticmethod
    def test_widget_replaced_in_nested_containers() -> None:
        state = {
            "child": FakeWidget("m1"),
            "nested": {"deep": [1, (FakeWidget("m2"), "x")]},
        }
        result = _replace_widget_refs(state)
        assert result == {
            "child": "anywidget:m1",
            "nested": {"deep": [1, ("anywidget:m2", "x")]},
        }

    @staticmethod
    def test_identity_preserved_when_no_widgets() -> None:
        state = {
            "records": [
                {"a": 1, "color": [255, 0, 0, 180]} for _ in range(50)
            ],
            "meta": ("x", 2, None),
        }
        result = _replace_widget_refs(state)
        assert result is state
        assert result["records"] is state["records"]
        assert result["records"][0] is state["records"][0]

    @staticmethod
    def test_replacement_copies_only_containers_on_the_path() -> None:
        untouched_sibling = {"big": [1, 2, 3]}
        state = {"sibling": untouched_sibling, "w": FakeWidget("m3")}
        result = _replace_widget_refs(state)
        assert result is not state
        assert result["w"] == "anywidget:m3"
        # Sibling subtree is the original object, not a copy.
        assert result["sibling"] is untouched_sibling
        # Input state is not mutated.
        assert isinstance(state["w"], FakeWidget)

    @staticmethod
    def test_tuple_replacement_returns_tuple() -> None:
        result = _replace_widget_refs((FakeWidget("m4"), 1))
        assert result == ("anywidget:m4", 1)
        assert isinstance(result, tuple)

    @staticmethod
    def test_empty_containers() -> None:
        for empty in ({}, [], ()):
            assert _replace_widget_refs(empty) is empty


class TestAnyWidgetStateSerializer:
    @staticmethod
    def test_enabled_for_anywidget_state() -> None:
        state = {"_esm": "export default {}", "w": FakeWidget("m5")}
        serializer = AnyWidgetStateSerializer(state)
        assert serializer.serialize(state)["w"] == "anywidget:m5"

    @staticmethod
    def test_disabled_for_non_anywidget_state() -> None:
        state = {"value": FakeWidget("m6")}
        serializer = AnyWidgetStateSerializer(state)
        # Not an anywidget comm: state passes through untouched.
        result = serializer.serialize(state)
        assert result is state
        assert isinstance(result["value"], FakeWidget)
