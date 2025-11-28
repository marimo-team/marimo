# tests/_runtime/app/conftest.py
import pytest


@pytest.fixture
def force_notebook_mode(monkeypatch):
    """Force embed() to take the interactive (notebook) path."""
    from marimo._runtime.context import utils as ctx_utils

    monkeypatch.setattr(ctx_utils, "running_in_notebook", lambda: True)
    return True


@pytest.fixture
def force_script_mode(monkeypatch):
    """Force embed() to take the script path."""
    from marimo._runtime.context import utils as ctx_utils

    monkeypatch.setattr(ctx_utils, "running_in_notebook", lambda: False)
    return True


@pytest.fixture
def list_cell_ids():
    def _list_cell_ids(app):
        return [cid for cid, _ in app.cell_manager.valid_cells()]

    return _list_cell_ids


@pytest.fixture
def build_child_app():
    def _build_child_app(static_ref: bool = True):
        import marimo as mo

        child = mo.App()

        @child.cell
        def __():
            import marimo as mo  # noqa: F401

            child_exec_count_A = 0
            child_exec_count_B = 0
            child_seen_x = None
            child_seen_theme = None
            return (
                mo,
                child_exec_count_A,
                child_exec_count_B,
                child_seen_x,
                child_seen_theme,
            )

        if static_ref:

            @child.cell
            def __(mo, child_exec_count_A, child_seen_x, child_seen_theme):
                # STATIC reference so analyzer records a dependency on `parent`.
                try:
                    _parent = parent  # noqa: F821
                except NameError:
                    _parent = None

                child_exec_count_A += 1
                x_from_parent = getattr(_parent, "x", None)
                theme_from_parent = getattr(_parent, "theme", None)

                child_seen_x = x_from_parent
                child_seen_theme = theme_from_parent

                view = mo.md(
                    f"child(A): x={x_from_parent}, theme={theme_from_parent}"
                )
                return (
                    child_exec_count_A,
                    child_seen_x,
                    child_seen_theme,
                    view,
                )
        else:

            @child.cell
            def __(mo, child_exec_count_A, child_seen_x, child_seen_theme):
                # DYNAMIC lookup: no static ref → no dependency edge (by design).
                _parent = globals().get("parent", None)

                child_exec_count_A += 1
                x_from_parent = getattr(_parent, "x", None)
                theme_from_parent = getattr(_parent, "theme", None)

                child_seen_x = x_from_parent
                child_seen_theme = theme_from_parent

                view = mo.md(
                    f"child(A-dyn): x={x_from_parent}, theme={theme_from_parent}"
                )
                return (
                    child_exec_count_A,
                    child_seen_x,
                    child_seen_theme,
                    view,
                )

        @child.cell
        def __(mo, child_exec_count_B):
            # Independent cell: never references `parent`; should not re-run.
            child_exec_count_B += 1
            noop_view = mo.md("child(B)")
            return child_exec_count_B, noop_view

        return child

    return _build_child_app


@pytest.fixture
def build_parent_app():
    def _build_parent_app(
        # child_app
    ):
        import marimo as mo

        parent = mo.App()

        @parent.cell
        def __():
            import marimo as mo  # noqa: F401
            from marimo import App  # noqa: F401

            x_input = 1
            theme_input = "light"
            parent_exec_count_x = 0
            parent_exec_count_embed = 0
            child_seen_from_parent = None
            return (
                mo,
                App,
                x_input,
                theme_input,
                parent_exec_count_x,
                parent_exec_count_embed,
                child_seen_from_parent,
            )

        @parent.cell
        def __(x_input, theme_input, parent_exec_count_x):
            # Defines `x` and `theme` — names that will be exposed.
            parent_exec_count_x += 1
            x = x_input
            theme = theme_input
            return x, theme, parent_exec_count_x

        @parent.cell
        async def __(
            mo,
            child_app,
            x,
            theme,
            parent_exec_count_embed,
            child_seen_from_parent,
        ):
            # Embed with read-only namespace "parent".
            parent_exec_count_embed += 1
            result = await child_app.embed(
                expose={"x": x, "theme": theme},
                namespace="parent",
                readonly=True,
            )

            # Convenience for script-mode test (child defs snapshot).
            try:
                child_seen_from_parent = result.defs["child_seen_x"]
            except Exception:
                pass

            ui = mo.vstack(
                [mo.md(f"parent: x={x}, theme={theme}"), result.output]
            )
            mo.vstack([ui])
            return parent_exec_count_embed, child_seen_from_parent

        return parent

    return _build_parent_app


@pytest.fixture
def run_all_cells(list_cell_ids):
    async def _run_all_cells(app):
        runner = app._get_kernel_runner()  # internal, OK in tests
        ids = list_cell_ids(app)
        await runner.run(set(ids))
        return runner, ids

    return _run_all_cells


@pytest.fixture
def run_only_cells():
    async def _run_only_cells(app, ids_subset):
        runner = app._get_kernel_runner()
        await runner.run(set(ids_subset))
        return runner

    return _run_only_cells
