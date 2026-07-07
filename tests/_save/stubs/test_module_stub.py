# Copyright 2026 Marimo. All rights reserved.
"""Tests for ModuleStub — name-based serialization of module objects."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from marimo._save.stubs.module_stub import MissingModule, ModuleStub

if TYPE_CHECKING:
    from pathlib import Path


class TestModuleStubLoad:
    @staticmethod
    def test_load_existing_module() -> None:
        """An importable module is returned as the real module."""
        import json

        stub = ModuleStub(json)
        assert stub.load() is json

    @staticmethod
    def test_missing_module_returns_placeholder() -> None:
        """A module absent from this environment restores to a
        MissingModule placeholder rather than raising."""
        stub = ModuleStub.__new__(ModuleStub)
        stub.name = "marimo_definitely_not_a_real_module_xyz"
        stub.hash = ""
        stub.version = ""
        result = stub.load()
        assert isinstance(result, MissingModule)
        assert result.__missing__ is True
        # Accessing an attribute surfaces the deferred import error.
        with pytest.raises(ModuleNotFoundError):
            _ = result.some_attr

    @staticmethod
    def test_transitive_import_failure_reraises(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A module that *exists* but fails on an internal import of a
        different missing module must NOT be masked as "this module is
        missing" — the real ModuleNotFoundError is re-raised."""
        mod_name = "_marimo_transitive_stub_test"
        (tmp_path / f"{mod_name}.py").write_text(
            "import a_module_that_truly_does_not_exist_zzz\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        sys.modules.pop(mod_name, None)
        try:
            stub = ModuleStub.__new__(ModuleStub)
            stub.name = mod_name
            stub.hash = ""
            stub.version = ""
            with pytest.raises(ModuleNotFoundError) as exc_info:
                stub.load()
            # The error is about the transitive dep, not our module.
            assert (
                exc_info.value.name == "a_module_that_truly_does_not_exist_zzz"
            )
        finally:
            sys.modules.pop(mod_name, None)
