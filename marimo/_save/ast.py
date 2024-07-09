# Copyright 2024 Marimo. All rights reserved.

import ast


class BlockException(Exception):
    pass


def compiled_ast(block):
    return compile(
        ast.Module(block, type_ignores=[]),
        # <ast> is non-standard as a filename, but easier to debug than <module>
        # <string> everywhere.
        "<ast>",
        mode="exec",
        flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        optimize=0,
        dont_inherit=True,
    )


def clean_to_module(pre_block, block):
    assert len(block.items) == 1
    initializer = block.items[0].context_expr
    if block.items[0].optional_vars:
        initializer = ast.Assign(
            targets=[block.items[0].optional_vars],
            value=initializer,
        )
    initializer.lineno = len(pre_block) + 1
    initializer.col_offset = 0
    pre_block.append(initializer)
    return (compiled_ast(pre_block), compiled_ast(block.body))


class ExtractWithBlock(ast.NodeTransformer):
    def __init__(self, lineno, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.lineno = lineno

    def generic_visit(self, node):
        transform = []
        on_line = []
        previous = None
        for n in node:
            if n.lineno < self.lineno:
                transform.append(n)
                previous = n
            elif n.lineno == self.lineno:
                on_line.append(n)
            else:
                break
        if len(on_line) == 0:
            if isinstance(previous, (ast.With, ast.If)):
                try:
                    return ExtractWithBlock(self.lineno).visit(previous.body)
                except BlockException:
                    on_line.append(previous)
            else:
                raise BlockException("Something wrong")
        if len(on_line) == 1:
            return clean_to_module(transform, on_line[0])
        # It should be possible to related the calling function with the AST
        # but reduces potential bugs by just throwing an error.
        raise Exception(
            "Saving on a shared line may lead to unexpected behavior."
        )
