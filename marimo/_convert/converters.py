# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import CellConfig
from marimo._ast.models import NotebookPayload
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

    # def to_markdown(self) -> str:
    #     """Convert to markdown format."""
    #     from marimo._convert.markdown.markdown import convert_from_ir_to_markdown

    #     return convert_from_ir_to_markdown(self.ir)

    def to_py(self) -> str:
        """Convert to python format."""
        from marimo._ast.app_config import _AppConfig
        from marimo._ast.codegen import generate_filecontents

        codes: list[str] = []
        names: list[str] = []
        cell_configs: list[CellConfig] = []
        config = _AppConfig(**self.ir.app.options)
        header_comments = self.ir.header.value if self.ir.header else None

        for cell in self.ir.cells:
            codes.append(cell.code)
            names.append(cell.name)
            cell_configs.append(
                CellConfig(
                    column=cell.options.get("column", 0),
                    disabled=cell.options.get("disabled", False),
                    hide_code=cell.options.get("hide_code", False),
                )
            )

        return generate_filecontents(
            NotebookPayload(
                codes=codes,
                names=names,
                cell_configs=cell_configs,
                config=config,
                header_comments=header_comments,
            )
        )

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
        from marimo._convert.markdown.markdown import convert_from_md

        # TODO: convert to IR instead of py file
        py_source = convert_from_md(source)
        return MarimoConvert.from_py(py_source)

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
