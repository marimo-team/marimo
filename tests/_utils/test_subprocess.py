# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from unittest.mock import patch

from marimo._utils.subprocess import safe_popen


class TestSafePopen:
    def test_successful_popen(self):
        proc = safe_popen(
            ["echo", "hello"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert proc is not None
        stdout, _ = proc.communicate()
        assert b"hello" in stdout
        proc.wait()

    def test_returns_none_on_file_not_found(self):
        result = safe_popen(["nonexistent_binary_abc123"])
        assert result is None

    def test_returns_none_on_permission_error(self):
        with patch(
            "subprocess.Popen", side_effect=PermissionError("not allowed")
        ):
            result = safe_popen(["echo", "hello"])
            assert result is None

    def test_returns_none_on_os_error(self):
        with patch(
            "subprocess.Popen",
            side_effect=OSError("some os error"),
        ):
            result = safe_popen(["echo", "hello"])
            assert result is None

    def test_returns_none_on_generic_exception(self):
        with patch(
            "subprocess.Popen",
            side_effect=RuntimeError("unexpected"),
        ):
            result = safe_popen(["echo", "hello"])
            assert result is None

    def test_passes_kwargs_through(self):
        proc = safe_popen(
            ["echo", "test"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        assert proc is not None
        stdout, _ = proc.communicate()
        assert "test" in stdout
        proc.wait()

    def test_returns_none_on_bad_cwd(self):
        result = safe_popen(
            ["echo", "hello"],
            cwd="/nonexistent/directory/abc123",
        )
        assert result is None
