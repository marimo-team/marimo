# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json

from marimo._messaging.notification import (
    AlertNotification,
    KernelStartupErrorNotification,
)
from marimo._server.api.endpoints.ws.ws_formatter import (
    format_wire_message,
    serialize_notification_for_websocket,
)


class TestFormatWireMessage:
    """Tests for format_wire_message function."""

    def test_basic_formatting(self) -> None:
        """Test basic wire message formatting."""
        op = "test-op"
        data = b'{"key": "value"}'
        result = format_wire_message(op, data)

        parsed = json.loads(result)
        assert parsed["op"] == "test-op"
        assert parsed["data"] == {"key": "value"}

    def test_with_nested_data(self) -> None:
        """Test formatting with nested JSON data."""
        op = "cell-op"
        data = b'{"cell_id": "abc123", "output": {"type": "text", "data": "hello"}}'
        result = format_wire_message(op, data)

        parsed = json.loads(result)
        assert parsed["op"] == "cell-op"
        assert parsed["data"]["cell_id"] == "abc123"
        assert parsed["data"]["output"]["type"] == "text"

    def test_with_special_characters_in_data(self) -> None:
        """Test formatting with special characters in data."""
        op = "alert"
        data = b'{"message": "Hello\\nWorld\\twith\\ttabs"}'
        result = format_wire_message(op, data)

        parsed = json.loads(result)
        assert parsed["op"] == "alert"
        assert parsed["data"]["message"] == "Hello\nWorld\twith\ttabs"

    def test_with_unicode_data(self) -> None:
        """Test formatting with unicode characters."""
        op = "notification"
        data = '{"text": "Hello 世界 🌍"}'.encode()
        result = format_wire_message(op, data)

        parsed = json.loads(result)
        assert parsed["op"] == "notification"
        assert parsed["data"]["text"] == "Hello 世界 🌍"

    def test_with_empty_object(self) -> None:
        """Test formatting with empty object data."""
        op = "empty"
        data = b"{}"
        result = format_wire_message(op, data)

        parsed = json.loads(result)
        assert parsed["op"] == "empty"
        assert parsed["data"] == {}


class TestSerializeNotificationForWebsocket:
    """Tests for serialize_notification_for_websocket function."""

    def test_kernel_startup_error_notification(self) -> None:
        """Test serializing KernelStartupErrorNotification."""
        notification = KernelStartupErrorNotification(
            error="Failed to start kernel: module not found"
        )
        result = serialize_notification_for_websocket(notification)

        parsed = json.loads(result)
        assert parsed["op"] == "kernel-startup-error"
        assert (
            parsed["data"]["error"]
            == "Failed to start kernel: module not found"
        )

    def test_alert_notification(self) -> None:
        """Test serializing AlertNotification."""
        notification = AlertNotification(
            title="Test Alert",
            description="This is a test alert message",
        )
        result = serialize_notification_for_websocket(notification)

        parsed = json.loads(result)
        assert parsed["op"] == "alert"
        assert parsed["data"]["title"] == "Test Alert"
        assert parsed["data"]["description"] == "This is a test alert message"

    def test_alert_notification_with_variant(self) -> None:
        """Test serializing AlertNotification with danger variant."""
        notification = AlertNotification(
            title="Error",
            description="Something went wrong",
            variant="danger",
        )
        result = serialize_notification_for_websocket(notification)

        parsed = json.loads(result)
        assert parsed["op"] == "alert"
        assert parsed["data"]["variant"] == "danger"

    def test_produces_valid_json(self) -> None:
        """Test that output is always valid JSON."""
        notification = KernelStartupErrorNotification(
            error='Error with "quotes" and special chars: <>&'
        )
        result = serialize_notification_for_websocket(notification)

        # Should not raise
        parsed = json.loads(result)
        assert "op" in parsed
        assert "data" in parsed


class TestIntegration:
    """Integration tests for the ws_formatter module."""

    def test_roundtrip_matches_expected_wire_format(self) -> None:
        """Test that the wire format matches what the frontend expects.

        The frontend expects messages in the format:
        {"op": "operation-name", "data": {...notification fields...}}
        """
        notification = KernelStartupErrorNotification(error="test error")
        result = serialize_notification_for_websocket(notification)

        parsed = json.loads(result)

        # Verify structure matches expected wire format
        assert set(parsed.keys()) == {"op", "data"}
        assert isinstance(parsed["op"], str)
        assert isinstance(parsed["data"], dict)

        # Verify op matches notification name
        assert parsed["op"] == notification.name
        assert parsed["op"] == "kernel-startup-error"
