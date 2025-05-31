# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._schemas.notebook import NotebookV1
from marimo._schemas.serialization import (
    EMPTY_NOTEBOOK_SERIALIZATION,
    NotebookSerialization,
)


class MarimoConverterIntermediate:
    """Intermediate representation that allows chaining conversions."""

    def __init__(self, ir: NotebookSerialization):
        self.ir = ir

    def to_notebook_v1(self) -> NotebookV1:
        """Convert to NotebookV1 format."""
        from marimo._convert.notebook import convert_from_ir_to_notebook_v1

        return convert_from_ir_to_notebook_v1(self.ir)

    def to_markdown(self) -> str:
        raise NotImplementedError("Not implemented")

    def to_py(self) -> str:
        """Convert to python format."""
        from marimo._ast.codegen import generate_filecontents_from_ir

        return generate_filecontents_from_ir(self.ir)

    def to_ir(self) -> NotebookSerialization:
        """Convert to notebook IR."""
        return self.ir


class MarimoConvert:
    """Converter utility for marimo notebooks."""

    @staticmethod
    def from_py(source: str) -> MarimoConverterIntermediate:
        """Convert from marimo Python source code.

        Args:
            source: Python source code string
        """
        from marimo._ast.parse import parse_notebook

        ir = parse_notebook(source) or EMPTY_NOTEBOOK_SERIALIZATION
        return MarimoConverterIntermediate(ir)

    @staticmethod
    def from_md(source: str) -> MarimoConverterIntermediate:
        """Convert from markdown source code.

        Args:
            source: Markdown source code string
        """
        from marimo._convert.markdown.markdown import (
            convert_from_md_to_marimo_ir,
        )

        return MarimoConvert.from_ir(convert_from_md_to_marimo_ir(source))

    @staticmethod
    def from_ipynb(source: str) -> MarimoConverterIntermediate:
        """Convert from Jupyter notebook JSON.

        Args:
            source: Jupyter notebook JSON string
        """
        from marimo._convert.ipynb import convert_from_ipynb_to_notebook_ir

        return MarimoConvert.from_ir(convert_from_ipynb_to_notebook_ir(source))

    @staticmethod
    def from_notebook_v1(
        notebook_v1: NotebookV1,
    ) -> MarimoConverterIntermediate:
        """Convert from notebook v1.

        Args:
            notebook_v1: Notebook v1
        """
        from marimo._convert.notebook import convert_from_notebook_v1_to_ir

        return MarimoConverterIntermediate(
            convert_from_notebook_v1_to_ir(notebook_v1)
        )

    @staticmethod
    def from_ir(ir: NotebookSerialization) -> MarimoConverterIntermediate:
        """Convert from notebook IR.

        Args:
            ir: Notebook IR
        """
        return MarimoConverterIntermediate(ir)
