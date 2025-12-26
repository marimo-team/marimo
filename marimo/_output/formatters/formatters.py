# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable

from marimo import _loggers
from marimo._config.config import Theme
from marimo._output.formatters.ai_formatters import (
    GoogleAiFormatter,
    OpenAIFormatter,
    TransformersFormatter,
)
from marimo._output.formatters.altair_formatters import AltairFormatter
from marimo._output.formatters.anywidget_formatters import AnyWidgetFormatter
from marimo._output.formatters.arviz_formatters import ArviZFormatter
from marimo._output.formatters.bokeh_formatters import BokehFormatter
from marimo._output.formatters.cell import CellFormatter
from marimo._output.formatters.df_formatters import (
    IbisFormatter,
    PolarsFormatter,
    PyArrowFormatter,
    PySparkFormatter,
)
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.holoviews_formatters import HoloViewsFormatter
from marimo._output.formatters.ipython_formatters import IPythonFormatter
from marimo._output.formatters.ipywidgets_formatters import IPyWidgetsFormatter
from marimo._output.formatters.leafmap_formatters import LeafmapFormatter
from marimo._output.formatters.lets_plot_formatters import LetsPlotFormatter
from marimo._output.formatters.matplotlib_formatters import MatplotlibFormatter
from marimo._output.formatters.pandas_formatters import PandasFormatter
from marimo._output.formatters.panel_formatters import PanelFormatter
from marimo._output.formatters.plotly_formatters import PlotlyFormatter
from marimo._output.formatters.pyecharts_formatters import PyechartsFormatter
from marimo._output.formatters.pygwalker_formatters import PygWalkerFormatter
from marimo._output.formatters.seaborn_formatters import SeabornFormatter
from marimo._output.formatters.structures import StructuresFormatter
from marimo._output.formatters.sympy_formatters import SympyFormatter
from marimo._output.formatters.tqdm_formatters import TqdmFormatter
from marimo._utils.site_packages import is_local_module

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence

# Map from formatter factory's package name to formatter, for third-party
# modules. These formatters will be registered if and when their associated
# packages are imported.
THIRD_PARTY_FACTORIES: dict[str, FormatterFactory] = {
    AltairFormatter.package_name(): AltairFormatter(),
    MatplotlibFormatter.package_name(): MatplotlibFormatter(),
    IbisFormatter.package_name(): IbisFormatter(),
    PandasFormatter.package_name(): PandasFormatter(),
    PolarsFormatter.package_name(): PolarsFormatter(),
    PyArrowFormatter.package_name(): PyArrowFormatter(),
    PySparkFormatter.package_name(): PySparkFormatter(),
    PygWalkerFormatter.package_name(): PygWalkerFormatter(),
    PlotlyFormatter.package_name(): PlotlyFormatter(),
    SeabornFormatter.package_name(): SeabornFormatter(),
    LeafmapFormatter.package_name(): LeafmapFormatter(),
    BokehFormatter.package_name(): BokehFormatter(),
    HoloViewsFormatter.package_name(): HoloViewsFormatter(),
    IPythonFormatter.package_name(): IPythonFormatter(),
    IPyWidgetsFormatter.package_name(): IPyWidgetsFormatter(),
    AnyWidgetFormatter.package_name(): AnyWidgetFormatter(),
    ArviZFormatter.package_name(): ArviZFormatter(),
    TqdmFormatter.package_name(): TqdmFormatter(),
    LetsPlotFormatter.package_name(): LetsPlotFormatter(),
    SympyFormatter.package_name(): SympyFormatter(),
    PyechartsFormatter.package_name(): PyechartsFormatter(),
    PanelFormatter.package_name(): PanelFormatter(),
    GoogleAiFormatter.package_name(): GoogleAiFormatter(),
    OpenAIFormatter.package_name(): OpenAIFormatter(),
    TransformersFormatter.package_name(): TransformersFormatter(),
}

# Formatters for builtin types and other things that don't require a
# third-party module import. These formatters' register methods need to be
# fast: we don't want their registration to noticeably delay program start-up.
NATIVE_FACTORIES: Sequence[FormatterFactory] = [
    CellFormatter(),
    StructuresFormatter(),
]


def patch_finder(
    finder: Any,
    third_party_factories: dict[str, FormatterFactory] | None = None,
    theme: Theme = "light",
) -> None:
    """Patch a MetaPathFinder to register formatters for third-parties.
    Python's import logic has roughly the following logic:
      1. search for a module; if found, create a "module spec" that knows
         how to create and load the module.
      2. use the spec's loader to load the module.

    We monkey-patch the first step to check if a searched-for module
    has a registered formatter. If a registered formatter is found,
    our patch in turn patches the loader to run the formatter after
    the module is exec'd.

    Because Python's import system caches modules, our formatters'
    register methods will be called at most once.
    """
    if third_party_factories is None:
        third_party_factories = THIRD_PARTY_FACTORIES
    # Note: "Vendored" dependencies may not have a find_spec method.
    # E.g. `six` bundled with a project.
    original_find_spec = getattr(finder, "find_spec", None)
    if original_find_spec is None:
        return

    # Method stub ignores typing for "self" to allow binding.
    def find_spec(  # type:ignore[no-untyped-def]
        self,
        fullname,
        path=None,
        target=None,
    ) -> Any:
        del self
        spec = original_find_spec(fullname, path, target)
        if spec is None:
            return spec

        # Skip patching for local modules (not under site-packages)
        if is_local_module(spec):
            return spec

        if spec.loader is not None and fullname in third_party_factories:
            # We're now in the process of importing a module with
            # an associated formatter factory. We'll hook into its
            # loader to register the formatters.
            original_exec_module = spec.loader.exec_module
            factory = third_party_factories[fullname]

            # We use kwargs instead of closing over the variables
            # `original_exec_module` and `factory` to force binding.
            def exec_module(
                module: Any,
                original_exec_module: Callable[
                    ..., Any
                ] = original_exec_module,
                factory: FormatterFactory = factory,
            ) -> Any:
                loader_return_value = original_exec_module(module)
                factory.register()
                factory.apply_theme_safe(theme)
                return loader_return_value

            spec.loader.exec_module = exec_module

        return spec

    # Recursive wrap can lead to a stack overflow in long running apps.
    # `find_spec` is dynamic, so just compare the __module__s
    module_name = getattr(finder.find_spec, "__module__", None)
    if hasattr(finder.find_spec, "__func__"):
        module_name = finder.find_spec.__module__

    # Only patch the finder if the module it was defined in is
    # different from the current module (`find_spec.__module__`)
    # i.e., only patch the finder if it isn't already patched
    if module_name != find_spec.__module__:
        # Use the __get__ descriptor to bind find_spec to this finder object,
        # to make sure self/cls gets passed
        finder.find_spec = find_spec.__get__(finder)  # type: ignore[method-assign]  # noqa: E501


def register_formatters(theme: Theme = "light") -> None:
    """Register formatters with marimo.

    marimo comes packaged with rich formatters for a number of third-party
    libraries. This function hooks into Python's import system to register
    these formatters with the kernel if and when a supported third-party
    library is imported into a marimo notebook.

    Hooking into the import system is more complicated than the alternative
    of checking whether a package is installed (by importing it) and then
    registering its formatters at kernel start-up. However, because some
    packages imports take a long time, this alternative would add considerable
    delay at program start-up, as the kernel would block as it registered
    all formatters before running the notebook. Hooking into the import
    system makes formatter registration completely lazy, improving
    UX at the cost of increased complexity that we have to maintain. In this
    case, the trade-off is worth it.
    """

    # For modules that are already imported, register their formatters
    # immediately; their import hook wouldn't be triggered since they are
    # already imported. This is relevant when executing as a script.
    pre_registered: set[str] = set()
    for package, factory in THIRD_PARTY_FACTORIES.items():
        if package in sys.modules:
            factory.register()
            factory.apply_theme_safe(theme)
            pre_registered.add(package)

    third_party_factories = {
        package: factory
        for package, factory in THIRD_PARTY_FACTORIES.items()
        if package not in pre_registered
    }

    # We loop over all MetaPathFinders, monkey-patching them to run third-party
    # formatters whenever a supported third-party package is imported (in
    # particular, when its module is exec'd). This ensures that formatters are
    # loaded at the last possible moment: when its package is imported.
    for finder in sys.meta_path:
        patch_finder(
            finder,
            third_party_factories=third_party_factories,
            theme=theme,
        )

    # These factories are for builtins or other things that don't require a
    # package import. So we can register them at program start-up.
    for factory in NATIVE_FACTORIES:
        factory.register()
        factory.apply_theme_safe(theme)
