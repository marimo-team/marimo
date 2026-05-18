# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use(
    "Agg"
)  # Non-interactive backend; avoids DPR pre-inflation on HiDPI hosts.


@pytest.mark.requires("matplotlib")
class TestSyncWebSocket:
    """Test the _SyncWebSocket adapter that bridges FigureManager to MarimoComm."""

    def _make_ws(self) -> tuple[Any, MagicMock]:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _SyncWebSocket,
        )

        mock_comm = MagicMock()
        ws = _SyncWebSocket(mock_comm)
        return ws, mock_comm

    def test_send_json(self) -> None:
        ws, mock_comm = self._make_ws()
        ws.send_json({"type": "figure_size", "width": 640})
        mock_comm.send.assert_called_once_with(
            data={
                "method": "custom",
                "content": {
                    "type": "json",
                    "data": {"type": "figure_size", "width": 640},
                },
            },
        )

    def test_send_binary(self) -> None:
        ws, mock_comm = self._make_ws()
        blob = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        ws.send_binary(blob)
        mock_comm.send.assert_called_once_with(
            data={
                "method": "custom",
                "content": {"type": "binary"},
            },
            buffers=[blob],
        )


@pytest.mark.requires("matplotlib")
class TestHandleCommMsg:
    """Test message parsing in mpl_interactive._handle_comm_msg.

    The comm payload from ModelCommand.into_comm_payload() is nested:
      {"content": {"data": {"method": "custom", "content": <mpl_event>}}}
    """

    def _make_element(self) -> Any:
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            mpl_interactive,
        )

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            element = mpl_interactive(fig)
        return element, fig

    def _wrap_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Wrap an mpl event in the ModelCommand payload structure."""
        return {
            "content": {
                "data": {
                    "method": "custom",
                    "content": event,
                },
            },
        }

    def test_supports_binary_ignored(self) -> None:
        element, fig = self._make_element()
        # Should not raise
        element._handle_comm_msg(
            self._wrap_event({"type": "supports_binary", "value": True})
        )
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_mouse_event_forwarded(self) -> None:
        element, fig = self._make_element()
        event = {
            "type": "motion_notify",
            "x": 100,
            "y": 200,
            "figure_id": str(id(fig)),
        }
        with patch.object(
            element._figure_manager, "handle_json"
        ) as mock_handle:
            element._handle_comm_msg(self._wrap_event(event))
            mock_handle.assert_called_once_with(event)

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_download_request(self) -> None:
        element, fig = self._make_element()
        with patch.object(element, "_handle_download") as mock_dl:
            element._handle_comm_msg(
                self._wrap_event({"type": "download", "format": "svg"})
            )
            mock_dl.assert_called_once_with("svg")

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_download_default_format(self) -> None:
        element, fig = self._make_element()
        with patch.object(element, "_handle_download") as mock_dl:
            element._handle_comm_msg(self._wrap_event({"type": "download"}))
            mock_dl.assert_called_once_with("png")

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_empty_message_does_not_crash(self) -> None:
        element, fig = self._make_element()
        # Empty message — no "type" key, should still call handle_json
        with patch.object(
            element._figure_manager, "handle_json"
        ) as mock_handle:
            element._handle_comm_msg({"content": {"data": {}}})
            mock_handle.assert_called_once_with({})

        import matplotlib.pyplot as plt

        plt.close(fig)


@pytest.mark.requires("matplotlib")
class TestHandleDownload:
    """Test that _handle_download renders the figure and sends it via comm."""

    def test_download_produces_valid_png(self) -> None:
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            mpl_interactive,
        )

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            element = mpl_interactive(fig)

        sent_data: list[dict[str, Any]] = []
        sent_buffers: list[list[Any]] = []

        def capture_send(data: Any, buffers: Any = None) -> None:
            sent_data.append(data)
            sent_buffers.append(buffers or [])

        element._comm.send = capture_send  # type: ignore[assignment]

        element._handle_download("png")

        assert len(sent_data) == 1
        assert sent_data[0]["content"]["type"] == "download"
        assert sent_data[0]["content"]["format"] == "png"
        assert len(sent_buffers[0]) == 1
        # Verify it's valid PNG
        assert sent_buffers[0][0][:4] == b"\x89PNG"

        plt.close(fig)


@pytest.mark.requires("matplotlib")
class TestDpiPreservationOnRerun:
    """Re-running a cell that wraps the same figure should not compound DPI.

    matplotlib's ``FigureCanvasBase.__init__`` unconditionally captures
    ``figure._original_dpi = figure.dpi``. After a HiDPI client connects
    and scales ``figure.dpi`` up by the device pixel ratio, a subsequent
    canvas creation on the same figure would treat that scaled value as
    "original" and scale it again — making the resolution compound on
    every rerun (see issue #9466).
    """

    def test_dpi_does_not_compound_across_reruns(self) -> None:
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _MplCleanupHandle,
            mpl_interactive,
        )

        fig, ax = plt.subplots(figsize=(5, 5), dpi=100)
        ax.plot([1, 2, 3])

        for _ in range(3):
            with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
                element = mpl_interactive(fig)

            # Simulate the HiDPI handshake from the frontend.
            element._figure_manager.handle_json(
                {"type": "set_device_pixel_ratio", "device_pixel_ratio": 2}
            )
            element._figure_manager.handle_json(
                {"type": "resize", "width": 500, "height": 500}
            )
            # While the canvas is live, dpi reflects the device-scaled value.
            assert fig.dpi == 200
            assert tuple(fig.get_size_inches()) == (5.0, 5.0)

            # Simulate cell teardown — the cleanup handle is what marimo
            # registers via cell_lifecycle_registry; running it directly
            # avoids needing a live runtime context in the test.
            cleanup = _MplCleanupHandle(
                comm=element._comm,
                figure_manager=element._figure_manager,
                sync_ws=element._sync_ws,
                original_dpi=element._original_dpi,
                original_size_inches=element._original_size_inches,
            )
            cleanup.dispose(context=MagicMock(), deletion=False)

            # After dispose the figure is restored to the user's intent.
            assert fig.dpi == 100
            assert tuple(fig.get_size_inches()) == (5.0, 5.0)

        plt.close(fig)


@pytest.mark.requires("matplotlib")
class TestMplCleanupHandle:
    """Test that _MplCleanupHandle properly closes the comm."""

    def test_dispose_closes_comm(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _MplCleanupHandle,
        )

        mock_comm = MagicMock()
        handle = _MplCleanupHandle(
            mock_comm, original_dpi=100, original_size_inches=(5.0, 5.0)
        )
        result = handle.dispose(context=MagicMock(), deletion=False)

        assert result is True
        mock_comm.close.assert_called_once()

    def test_dispose_on_deletion(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _MplCleanupHandle,
        )

        mock_comm = MagicMock()
        handle = _MplCleanupHandle(
            mock_comm, original_dpi=100, original_size_inches=(5.0, 5.0)
        )
        result = handle.dispose(context=MagicMock(), deletion=True)

        assert result is True
        mock_comm.close.assert_called_once()

    def test_dispose_cleans_up_figure_manager(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _MplCleanupHandle,
        )

        mock_comm = MagicMock()
        mock_manager = MagicMock()
        # The disconnect helper iterates this; keep it empty so the mock
        # doesn't trip over MagicMock's default value generators.
        mock_manager.canvas.callbacks.callbacks = {}
        mock_ws = MagicMock()
        handle = _MplCleanupHandle(
            mock_comm,
            figure_manager=mock_manager,
            sync_ws=mock_ws,
            original_dpi=100,
            original_size_inches=(5.0, 5.0),
        )
        result = handle.dispose(context=MagicMock(), deletion=False)

        assert result is True
        mock_manager.remove_web_socket.assert_called_once_with(mock_ws)
        mock_comm.close.assert_called_once()

    def test_dispose_tolerates_manager_errors(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _MplCleanupHandle,
        )

        mock_comm = MagicMock()
        mock_manager = MagicMock()
        mock_manager.remove_web_socket.side_effect = RuntimeError("boom")
        # Force the disconnect path to blow up too.
        type(mock_manager.canvas).callbacks = property(
            lambda _self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        mock_ws = MagicMock()
        handle = _MplCleanupHandle(
            mock_comm,
            figure_manager=mock_manager,
            sync_ws=mock_ws,
            original_dpi=100,
            original_size_inches=(5.0, 5.0),
        )
        # Should not raise even if manager cleanup fails
        result = handle.dispose(context=MagicMock(), deletion=False)

        assert result is True
        mock_comm.close.assert_called_once()


@pytest.mark.requires("matplotlib")
class TestToolbarCallbackCleanup:
    """Disposing a cleanup handle must disconnect the toolbar's callbacks
    from the figure-shared event registry.

    `canvas.callbacks` is a property that delegates to
    `figure._canvas_callbacks`, so every canvas bound to the same figure
    shares one registry. Without explicit cleanup, each cell rerun stacks
    another `_zoom_pan_handler` on the registry — leading to duplicate
    `press_pan`/`release_pan` dispatch and ultimately the
    `AttributeError: 'Axes' object has no attribute '_pan_start'` from
    matplotlib's `Axes.end_pan`.
    """

    @staticmethod
    def _count_toolbar_handlers(fig: Any, signal: str) -> int:
        handlers = fig.canvas.callbacks.callbacks.get(signal, {})
        count = 0
        for ref in handlers.values():
            fn = ref() if callable(ref) else ref
            owner = getattr(fn, "__self__", None)
            if (
                owner is not None
                and type(owner).__name__ == "NavigationToolbar2WebAgg"
            ):
                count += 1
        return count

    def test_dispose_disconnects_toolbar_callbacks(self) -> None:
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _MplCleanupHandle,
            mpl_interactive,
        )

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            elem1 = mpl_interactive(fig)
        assert self._count_toolbar_handlers(fig, "button_press_event") == 1
        assert self._count_toolbar_handlers(fig, "button_release_event") == 1

        # Simulate cell teardown: marimo's runtime invokes dispose on the
        # lifecycle handle when the cell re-runs or is deleted.
        cleanup = _MplCleanupHandle(
            comm=elem1._comm,
            figure_manager=elem1._figure_manager,
            sync_ws=elem1._sync_ws,
            original_dpi=elem1._original_dpi,
            original_size_inches=elem1._original_size_inches,
        )
        cleanup.dispose(context=MagicMock(), deletion=False)

        # Simulate the cell re-running: a new mpl_interactive on the same
        # figure object. After dispose, only the new toolbar's callbacks
        # should be live on the shared registry.
        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            _elem2 = mpl_interactive(fig)

        assert self._count_toolbar_handlers(fig, "button_press_event") == 1
        assert self._count_toolbar_handlers(fig, "button_release_event") == 1

        plt.close(fig)


@pytest.mark.requires("matplotlib")
class TestMplInteractiveArgs:
    """Test that mpl_interactive passes correct args to the UIElement."""

    def test_initial_dimensions(self) -> None:
        import matplotlib
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            mpl_interactive,
        )

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot([1, 2, 3])

        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            element = mpl_interactive(fig)

        dpi = matplotlib.rcParams["figure.dpi"]
        expected_w = int(8 * dpi)
        expected_h = int(6 * dpi)
        # Args are rendered as data-* attributes in HTML
        assert f"data-width='{expected_w}'" in element.text
        assert f"data-height='{expected_h}'" in element.text

        plt.close(fig)

    def test_virtual_file_urls_in_args(self) -> None:
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            mpl_interactive,
        )

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            element = mpl_interactive(fig)

        # Args should contain URL references, not inline content
        assert "mpl-js-url" in element.text
        assert "css-url" in element.text
        assert "toolbar-images" in element.text
        # URLs should be virtual file paths or data URIs
        text = element.text
        assert ".js" in text or "data:" in text
        assert ".css" in text or "data:" in text

        plt.close(fig)

    def test_component_name(self) -> None:
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            mpl_interactive,
        )

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            element = mpl_interactive(fig)

        assert "marimo-mpl-interactive" in element.text
        plt.close(fig)

    def test_convert_value_returns_empty_dict(self) -> None:
        import matplotlib.pyplot as plt

        from marimo._plugins.ui._impl.from_mpl_interactive import (
            mpl_interactive,
        )

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        with patch("marimo._plugins.ui._impl.comm.broadcast_notification"):
            element = mpl_interactive(fig)

        assert element._convert_value({"model_id": "abc"}) == {}
        plt.close(fig)


class TestScopeCss:
    """Test that _scope_css uses native CSS nesting."""

    def test_wraps_rules_in_scope(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import _scope_css

        css = ".toolbar { display: flex; }\n.btn { color: red; }"
        result = _scope_css(css, ".my-scope")
        assert result.startswith(".my-scope {")
        assert result.endswith("}")
        assert ".toolbar { display: flex; }" in result
        assert ".btn { color: red; }" in result

    def test_keyframes_preserved(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import _scope_css

        css = "@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }"
        result = _scope_css(css, ".s")
        assert "@keyframes spin" in result

    def test_media_query_preserved(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import _scope_css

        css = "@media (max-width: 600px) { .x { display: none; } }"
        result = _scope_css(css, ".s")
        assert "@media (max-width: 600px)" in result


@pytest.mark.requires("matplotlib")
class TestCachedAssets:
    """Test that static assets are cached across instances."""

    def test_toolbar_images_cached(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _get_toolbar_images,
        )

        # Clear the cache to test from scratch
        _get_toolbar_images.cache_clear()

        images1 = _get_toolbar_images()
        images2 = _get_toolbar_images()
        assert images1 is images2
        assert len(images1) > 0
        # All values should be data URIs
        for key, val in images1.items():
            assert val.startswith("data:image/png;base64,"), key

    def test_mpl_css_content(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _get_mpl_css,
        )

        css = _get_mpl_css()
        assert isinstance(css, str)
        assert len(css) > 0
        # Should contain our custom overrides
        assert "mpl-toolbar" in css

    def test_patched_js_has_focus_patches(self) -> None:
        from marimo._plugins.ui._impl.from_mpl_interactive import (
            _get_patched_mpl_js,
        )

        js = _get_patched_mpl_js()
        assert "// canvas.focus();" in js
        assert "// canvas_div.focus();" in js
