# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Any, Callable, Sequence

from marimo._output.formatters.altair_formatters import AltairFormatter
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.matplotlib_formatters import MatplotlibFormatter
from marimo._output.formatters.pandas_formatters import PandasFormatter
from marimo._output.formatters.plotly_formatters import PlotlyFormatter
from marimo._output.formatters.seaborn_formatters import SeabornFormatter
from marimo._output.formatters.structures import StructuresFormatter

# Map from formatter factory's package name to formatter, for third-party
# modules. These formatters will be registered if and when their associated
# packages are imported.
THIRD_PARTY_FACTORIES: dict[str, FormatterFactory] = {
    AltairFormatter.package_name(): AltairFormatter(),
    MatplotlibFormatter.package_name(): MatplotlibFormatter(),
    PandasFormatter.package_name(): PandasFormatter(),
    PlotlyFormatter.package_name(): PlotlyFormatter(),
    SeabornFormatter.package_name(): SeabornFormatter(),
}

# Formatters for builtin types and other things that don't require a
# third-party module import. These formatters' register methods need to be
# fast: we don't want their registration to noticeably delay program start-up.
NATIVE_FACTORIES: Sequence[FormatterFactory] = [
    StructuresFormatter(),
]


def register_formatters() -> None:
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

    # We loop over all MetaPathFinders, monkey-patching them to run third-party
    # formatters whenever a supported third-party package is imported (in
    # particular, when its module is exec'd). This ensures that formatters are
    # loaded at the last possible moment: when its package is imported.
    #
    # Python's import logic has roughly the following logic:
    #   1. search for a module; if found, create a "module spec" that knows
    #      how to create and load the module.
    #   2. use the spec's loader to load the module.
    #
    # We monkey-patch the first step to check if a searched-for module
    # has a registered formatter. If a registered formatter is found,
    # our patch in turn patches the loader to run the formatter after
    # the module is exec'd.
    #
    # Because Python's import system caches modules, our formatters'
    # register methods will be called at most once.
    for finder in sys.meta_path:
        original_find_spec = finder.find_spec

        # We include `original_find_spec` as a kwarg to force it to be bound
        # to the new `find_spec` method; this is needed because closures are
        # late-binding and we're in a for loop ...
        def find_spec(  # type:ignore[no-untyped-def]
            fullname,
            path=None,
            target=None,
            original_find_spec=original_find_spec,
        ) -> Any:
            spec = original_find_spec(fullname, path, target)
            if spec is None:
                return spec

            if spec.loader is not None and fullname in THIRD_PARTY_FACTORIES:
                # We're now in the process of importing a module with
                # an associated formatter factory. We'll hook into its
                # loader to register the formatters.
                original_exec_module = spec.loader.exec_module
                factory = THIRD_PARTY_FACTORIES[fullname]

                # Once again, we use kwargs instead of closing over the
                # variables `original_exec_module` and `factory` to force
                # binding.
                def exec_module(
                    module: Any,
                    original_exec_module: Callable[
                        ..., Any
                    ] = original_exec_module,
                    factory: FormatterFactory = factory,
                ) -> Any:
                    loader_return_value = original_exec_module(module)
                    factory.register()
                    return loader_return_value

                spec.loader.exec_module = exec_module

            return spec

        finder.find_spec = find_spec  # type: ignore[method-assign]

    # These factories are for builtins or other things that don't require a
    # package import. So we can register them at program start-up.
    for factory in NATIVE_FACTORIES:
        factory.register()
