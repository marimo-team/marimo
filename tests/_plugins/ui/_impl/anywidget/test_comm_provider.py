# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager

HAS_DEPS = DependencyManager.anywidget.has() and DependencyManager.has("comm")


@pytest.mark.skipif(not HAS_DEPS, reason="anywidget/comm not installed")
class TestPatchCommCreate:
    @staticmethod
    def test_patches_comm_create() -> None:
        import comm

        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            patch_comm_create,
        )

        original = comm.create_comm
        patch_comm_create()
        assert comm.create_comm is not original
        # Restore
        comm.create_comm = original

    @staticmethod
    def test_anywidget_comm_returns_marimo_comm() -> None:
        import comm

        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            patch_comm_create,
        )
        from marimo._plugins.ui._impl.comm import MarimoComm

        original = comm.create_comm
        patch_comm_create()
        try:
            c = comm.create_comm(
                target_name="jupyter.widget",
                data={
                    "state": {
                        "_model_module": "anywidget",
                        "_model_name": "AnyModel",
                        "_esm": "export default {}",
                    },
                    "buffer_paths": [],
                },
            )
            assert isinstance(c, MarimoComm)
            assert c.esm == "export default {}"
            c.close()
        finally:
            comm.create_comm = original

    @staticmethod
    def test_non_anywidget_comm_returns_dummy() -> None:
        import comm
        from comm import DummyComm

        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            patch_comm_create,
        )

        original = comm.create_comm
        patch_comm_create()
        try:
            c = comm.create_comm(
                target_name="some.other.target",
                data={"state": {"foo": "bar"}},
            )
            assert isinstance(c, DummyComm)
        finally:
            comm.create_comm = original

    @staticmethod
    def test_idempotent() -> None:
        import comm

        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            patch_comm_create,
        )

        original = comm.create_comm
        patch_comm_create()
        first = comm.create_comm
        patch_comm_create()
        second = comm.create_comm
        # Second patch wraps the first — both should work
        assert first is not original
        assert second is not original
        comm.create_comm = original


@pytest.mark.skipif(not HAS_DEPS, reason="anywidget/comm not installed")
class TestMaybeAsAnywidgetHtml:
    @staticmethod
    def test_produces_html_for_anywidget_mimebundle() -> None:
        import comm

        from marimo._output.formatters.repr_formatters import (
            _maybe_as_anywidget_html,
        )
        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            patch_comm_create,
        )

        original = comm.create_comm
        patch_comm_create()
        try:
            esm = "export default { render({ el }) { el.textContent = 'hi'; } }"
            c = comm.create_comm(
                target_name="jupyter.widget",
                data={
                    "state": {
                        "_model_module": "anywidget",
                        "_model_name": "AnyModel",
                        "_esm": esm,
                    },
                    "buffer_paths": [],
                },
            )
            model_id = c.comm_id

            contents = {
                "application/vnd.jupyter.widget-view+json": {
                    "model_id": model_id,
                    "version_major": 2,
                },
            }
            result = _maybe_as_anywidget_html(contents)
            assert result is not None
            mime, html = result
            assert mime == "text/html"
            assert "marimo-anywidget" in html
            assert "marimo-ui-element" in html
            assert str(model_id) in html
            c.close()
        finally:
            comm.create_comm = original

    @staticmethod
    def test_returns_none_for_non_anywidget() -> None:
        from marimo._output.formatters.repr_formatters import (
            _maybe_as_anywidget_html,
        )

        contents = {
            "application/vnd.jupyter.widget-view+json": {
                "model_id": "nonexistent",
                "version_major": 2,
            },
        }
        assert _maybe_as_anywidget_html(contents) is None

    @staticmethod
    def test_returns_none_for_no_widget_view() -> None:
        from marimo._output.formatters.repr_formatters import (
            _maybe_as_anywidget_html,
        )

        assert _maybe_as_anywidget_html({"text/plain": "hello"}) is None
