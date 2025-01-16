from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Tuple

from marimo._mcp.server import MCPServer


class MCPParser:
    def __init__(self, server: MCPServer):
        self.server = server

    def parse_message(
        self, message: str
    ) -> List[Tuple[str, str, List[Any], Dict[str, Any]]]:
        """Parse a message and extract MCP function calls.

        Returns a list of tuples (type, name, args, kwargs) where:
        - type is one of: 'tool', 'resource', 'prompt'
        - name is the function/resource/prompt name
        - args is a list of positional arguments
        - kwargs is a dict of keyword arguments
        """
        functions = []

        # Find all MCP function calls
        patterns = {
            "tool": r"!(\w+)\((.*?)\)",
            "resource": r"@(\w+)\((.*?)\)",
            "prompt": r"/(\w+)\((.*?)\)",
        }

        for func_type, pattern in patterns.items():
            for match in re.finditer(pattern, message):
                name = match.group(1)
                args_str = match.group(2) if len(match.groups()) > 1 else ""

                try:
                    # Parse arguments as Python expressions
                    args_expr = f"dummy_func({args_str})"
                    parsed = ast.parse(args_expr)
                    call_node = parsed.body[0].value

                    # Extract args and kwargs
                    args = []
                    kwargs = {}

                    for arg in call_node.args:
                        args.append(ast.literal_eval(arg))

                    for kwarg in call_node.keywords:
                        kwargs[kwarg.arg] = ast.literal_eval(kwarg.value)

                    functions.append((func_type, name, args, kwargs))
                except (SyntaxError, ValueError):
                    # Skip invalid function calls
                    continue

        return functions

    async def execute_functions(
        self, functions: List[Tuple[str, str, List[Any], Dict[str, Any]]]
    ) -> List[str]:
        """Execute a list of MCP functions and return their results as strings."""
        results = []

        for func_type, name, args, kwargs in functions:
            try:
                if func_type == "tool":
                    result = await self.server.execute_tool(
                        name, *args, **kwargs
                    )
                    results.append(str(result))
                elif func_type == "resource":
                    result = await self.server.execute_resource(
                        name, *args, **kwargs
                    )
                    results.append(str(result))
                elif func_type == "prompt":
                    result = await self.server.execute_prompt(
                        name, *args, **kwargs
                    )
                    results.append(str(result))
            except Exception as e:
                results.append(f"Error executing {func_type} {name}: {str(e)}")

        return results

    async def process_message(self, message: str) -> Tuple[str, List[str]]:
        """Process a message, execute any MCP functions, and return the processed message and results."""
        functions = self.parse_message(message)
        results = await self.execute_functions(functions)

        # Replace function calls with their results
        processed_message = message
        for (func_type, name, _, _), result in zip(functions, results):
            pattern = f"{'!' if func_type == 'tool' else '@' if func_type == 'resource' else '/'}{name}\\(.*?\\)"
            processed_message = re.sub(
                pattern, result, processed_message, count=1
            )

        return processed_message, results
