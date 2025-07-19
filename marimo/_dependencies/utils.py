# Copyright 2024 Marimo. All rights reserved.

import re


def get_module_name(exception: ModuleNotFoundError) -> str:
    """
    Get the module name from a ModuleNotFoundError. Some errors do not have a
    name attribute (eg. a library that did not handle the error correctly), so we need to
    parse the error message.
    """
    module_name = exception.name

    if module_name is None:
        # Extract whatever is in quotes from the error message
        match = re.search(r"['\"]([^'\"]+)['\"]", str(exception))
        if match:
            module_name = match.group(1)

    if module_name is None:
        raise ValueError(
            f"Could not get module name from error message: {str(exception)}"
        )

    # If the module name is a submodule, we need to get the base module name
    module_name = module_name.split(".")[0]
    return module_name
