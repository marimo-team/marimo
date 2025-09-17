# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json

import msgspec
import pytest

from marimo._messaging.ops import (
    Alert,
    CompletedRun,
    Interrupted,
    deserialize_kernel_message,
    deserialize_kernel_operation_name,
    serialize_kernel_message,
)
from marimo._messaging.types import KernelMessage


class TestSerializeKernelMessage:
    def test_serialize_interrupted(self) -> None:
        """Test serializing an Interrupted message."""
        message = Interrupted()

        result = serialize_kernel_message(message)

        assert isinstance(result, bytes)

        parsed = json.loads(result.decode())
        assert parsed["op"] == "interrupted"

    def test_serialize_alert(self) -> None:
        """Test serializing an Alert message."""
        message = Alert(
            title="Test Alert",
            description="This is a test alert",
            variant="danger",
        )

        result = serialize_kernel_message(message)

        assert isinstance(result, bytes)

        parsed = json.loads(result.decode())
        assert parsed["op"] == "alert"
        assert parsed["title"] == "Test Alert"
        assert parsed["description"] == "This is a test alert"
        assert parsed["variant"] == "danger"


class TestDeserializeKernelMessage:
    def test_deserialize_interrupted(self) -> None:
        """Test deserializing an Interrupted message."""

        message_dict = {"op": "interrupted"}
        kernel_message = KernelMessage(json.dumps(message_dict).encode())

        result = deserialize_kernel_message(kernel_message)

        assert isinstance(result, Interrupted)

    def test_deserialize_alert(self) -> None:
        """Test deserializing an Alert message."""

        message_dict = {
            "op": "alert",
            "title": "Test Alert",
            "description": "This is a test alert",
            "variant": "danger",
        }
        kernel_message = KernelMessage(json.dumps(message_dict).encode())

        result = deserialize_kernel_message(kernel_message)

        assert isinstance(result, Alert)
        assert result.title == "Test Alert"
        assert result.description == "This is a test alert"
        assert result.variant == "danger"

    def test_deserialize_invalid_json(self) -> None:
        """Test deserializing invalid JSON should raise an error."""
        invalid_message = KernelMessage(b"invalid json")

        with pytest.raises(msgspec.DecodeError):
            assert deserialize_kernel_message(invalid_message)

    def test_deserialize_unknown_message_type(self) -> None:
        """Test deserializing unknown message type should raise an error."""

        message_dict = {"name": "unknown-message-type", "data": "some data"}
        kernel_message = KernelMessage(json.dumps(message_dict).encode())

        with pytest.raises(msgspec.ValidationError):
            assert deserialize_kernel_message(kernel_message)

    def test_deserialize_missing_required_fields(self) -> None:
        """Test deserializing message with missing required fields should raise an error."""

        message_dict = {
            "name": "kernel-ready"
            # Missing required fields: cell_ids, codes
        }
        kernel_message = KernelMessage(json.dumps(message_dict).encode())

        with pytest.raises(msgspec.ValidationError):
            assert deserialize_kernel_message(kernel_message)


class TestRoundTripSerialization:
    def test_round_trip_interrupted(self) -> None:
        """Test round-trip for Interrupted message."""
        original = Interrupted()

        serialized = serialize_kernel_message(original)
        deserialized = deserialize_kernel_message(serialized)

        assert isinstance(deserialized, Interrupted)

    def test_round_trip_alert(self) -> None:
        """Test round-trip for Alert message."""
        original = Alert(
            title="Warning",
            description="Something went wrong",
            variant="danger",
        )

        serialized = serialize_kernel_message(original)
        deserialized = deserialize_kernel_message(serialized)

        assert isinstance(deserialized, Alert)
        assert deserialized.title == original.title
        assert deserialized.description == original.description
        assert deserialized.variant == original.variant

    def test_round_trip_with_unicode(self) -> None:
        """Test round-trip with unicode characters."""
        original = Alert(
            title="测试标题",
            description="Тестовое описание with émojis 🚀",
            variant="danger",
        )

        serialized = serialize_kernel_message(original)
        deserialized = deserialize_kernel_message(serialized)

        assert isinstance(deserialized, Alert)
        assert deserialized.title == original.title
        assert deserialized.description == original.description
        assert deserialized.variant == original.variant


def test_deserialize_kernel_operation_name() -> None:
    """Test deserializing a KernelOperationName message."""
    original = CompletedRun()
    serialized = serialize_kernel_message(original)
    assert deserialize_kernel_operation_name(serialized) == "completed-run"
