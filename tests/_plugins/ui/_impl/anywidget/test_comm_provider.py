# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._dependencies.dependencies import DependencyManager

HAS_DEPS = DependencyManager.anywidget.has() and DependencyManager.has("comm")


@pytest.mark.skipif(not HAS_DEPS, reason="anywidget/comm not installed")
class TestPatchCommCreate:
    @staticmethod
    def test_patches_comm_create() -> None:
        import comm

        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            install_anywidget_comm_provider,
        )

        original = comm.create_comm
        comm.create_comm = comm.DummyComm
        try:
            install_anywidget_comm_provider()
            assert comm.create_comm is not comm.DummyComm
        finally:
            comm.create_comm = original

    @staticmethod
    def test_anywidget_comm_returns_marimo_comm() -> None:
        import comm

        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            install_anywidget_comm_provider,
        )
        from marimo._plugins.ui._impl.comm import MarimoComm

        original = comm.create_comm
        install_anywidget_comm_provider()
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
            # The comm mints the ESM spec at open (used later by repr
            # formatters); the raw source itself is not kept.
            from marimo._utils.code import hash_code

            assert c.esm_spec is not None
            assert c.esm_spec.hash == hash_code("export default {}")
            c.close()
        finally:
            comm.create_comm = original

    @staticmethod
    def test_non_anywidget_comm_returns_dummy() -> None:
        import comm
        from comm import DummyComm

        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            install_anywidget_comm_provider,
        )

        original = comm.create_comm
        install_anywidget_comm_provider()
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
            install_anywidget_comm_provider,
        )

        original = comm.create_comm
        comm.create_comm = comm.DummyComm
        try:
            install_anywidget_comm_provider()
            first = comm.create_comm
            install_anywidget_comm_provider()
            assert comm.create_comm is first
        finally:
            comm.create_comm = original

    @staticmethod
    def test_register_formatters_installs_provider_without_anywidget() -> None:
        import comm

        from marimo._output.formatters.formatters import register_formatters

        original = comm.create_comm
        anywidget = sys.modules.pop("anywidget", None)
        comm.create_comm = comm.DummyComm
        try:
            register_formatters()
            assert comm.create_comm is not comm.DummyComm
            assert "anywidget" not in sys.modules
        finally:
            comm.create_comm = original
            if anywidget is not None:
                sys.modules["anywidget"] = anywidget


@pytest.mark.skipif(not HAS_DEPS, reason="anywidget/comm not installed")
class TestMaybeAsAnywidgetHtml:
    @staticmethod
    def test_produces_html_for_anywidget_mimebundle() -> None:
        import comm

        from marimo._output.formatters.repr_formatters import (
            _maybe_as_anywidget_html,
        )
        from marimo._plugins.ui._impl.anywidget.comm_provider import (
            install_anywidget_comm_provider,
        )

        original = comm.create_comm
        install_anywidget_comm_provider()
        try:
            esm = (
                "export default { render({ el }) { el.textContent = 'hi'; } }"
            )
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
