# Copyright 2026 Marimo. All rights reserved.
"""Jupyter notebook (.ipynb) conversion utilities for marimo notebooks.

This module provides bidirectional conversion between ipynb and marimo IR:
- `to_ir`: Parse Jupyter notebooks into marimo notebook IR
- `from_ir`: Export marimo notebook IR to Jupyter notebook format
"""

from __future__ import annotations

from marimo._convert.ipynb.from_ir import convert_from_ir_to_ipynb
from marimo._convert.ipynb.to_ir import (
    CodeCell,
    ExclamationMarkResult,
    convert_from_ipynb_to_notebook_ir,
)

__all__ = [
    # Export (IR → ipynb)
    "convert_from_ir_to_ipynb",
    # Import (ipynb → IR)
    "convert_from_ipynb_to_notebook_ir",
    # Types
    "CodeCell",
    "ExclamationMarkResult",
]
