# Copyright 2025 Marimo. All rights reserved.
import builtins

BUILTINS = set(
    {
        *set(builtins.__dict__.keys()),
        # resolved from:
        #   set(globals().keys()) - set(builtins.__dict__.keys())
        "__builtin__",
        "__file__",
        "__builtins__",
    }
)
