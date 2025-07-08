# Copyright 2024 Marimo. All rights reserved.
"""
SAMPLE BACKEND TOOL - This file is commented out as an example.

This file demonstrates how to create a backend tool for the marimo AI system.
Backend tools are functions that run on the server and can be called by the AI
during conversations.

To create your own backend tool:
1. Copy this file and rename it
2. Uncomment the code
3. Modify the tool definition and handler function
4. Import and register it in __init__.py

Backend tools are useful for:
- Server-side operations that require access to the filesystem
- Database queries
- API calls to external services
- System information gathering
- File operations
"""

# from __future__ import annotations
#
# from typing import Any
#
# from marimo import _loggers
# from ..tools import get_tool_manager, Tool
#
# LOGGER = _loggers.marimo_logger()
#
#
# def validate_sample_tool_parameters(arguments: dict[str, Any]) -> tuple[bool, str]:
#     """
#     Validate parameters for the sample tool.
#
#     This function is optional but recommended for robust parameter validation.
#
#     Args:
#         arguments: The arguments to validate
#
#     Returns:
#         Tuple of (is_valid, error_message). If is_valid is True, error_message is empty.
#     """
#     # Define valid parameter names and their expected types
#     valid_params = {
#         "message": str,
#         "count": int,
#         "uppercase": bool,
#     }
#
#     # Check for required parameters
#     required_params = {"message"}
#     missing_params = required_params - set(arguments.keys())
#     if missing_params:
#         error_msg = f"Missing required parameters: {', '.join(missing_params)}"
#         return False, error_msg
#
#     # Check for unknown parameters
#     unknown_params = set(arguments.keys()) - set(valid_params.keys())
#     if unknown_params:
#         error_msg = f"Unknown parameters: {', '.join(unknown_params)}. Valid parameters are: {', '.join(valid_params.keys())}"
#         return False, error_msg
#
#     # Validate parameter types
#     for param_name, param_value in arguments.items():
#         expected_type = valid_params[param_name]
#         if not isinstance(param_value, expected_type):
#             error_msg = f"Parameter '{param_name}' must be of type {expected_type.__name__}, got {type(param_value).__name__}"
#             return False, error_msg
#
#     # Custom validation logic
#     if "count" in arguments and arguments["count"] < 1:
#         return False, "Parameter 'count' must be greater than 0"
#
#     if "count" in arguments and arguments["count"] > 10:
#         return False, "Parameter 'count' must be 10 or less"
#
#     # All validation checks passed
#     return True, ""
#
#
# def register_sample_tool() -> None:
#     """Register a sample backend tool that demonstrates the basic pattern."""
#
#     # Define the tool with its schema
#     sample_tool = Tool(
#         name="sample_backend_tool",
#         description="A sample backend tool that processes text messages. This demonstrates how to create backend tools.",
#         parameters={
#             "type": "object",
#             "properties": {
#                 "message": {
#                     "type": "string",
#                     "description": "The message to process"
#                 },
#                 "count": {
#                     "type": "integer",
#                     "description": "Number of times to repeat the message",
#                     "default": 1,
#                     "minimum": 1,
#                     "maximum": 10
#                 },
#                 "uppercase": {
#                     "type": "boolean",
#                     "description": "Whether to convert the message to uppercase",
#                     "default": False
#                 }
#             },
#             "required": ["message"]
#         },
#         source="backend",  # This indicates it's a backend tool
#         mode=["ask", "chat"]  # Available in both ask and chat modes
#     )
#
#     def sample_tool_handler(arguments: dict[str, Any]) -> dict[str, Any]:
#         """
#         Handle the sample tool execution.
#
#         Args:
#             arguments: The validated arguments passed to the tool
#
#         Returns:
#             Dictionary containing the tool's response
#         """
#         try:
#             # Extract parameters with defaults
#             message = arguments["message"]
#             count = arguments.get("count", 1)
#             uppercase = arguments.get("uppercase", False)
#
#             # Process the message
#             processed_message = message.upper() if uppercase else message
#             result = [processed_message] * count
#
#             # Return structured response
#             return {
#                 "success": True,
#                 "original_message": message,
#                 "processed_messages": result,
#                 "settings": {
#                     "count": count,
#                     "uppercase": uppercase
#                 },
#                 "total_characters": sum(len(msg) for msg in result)
#             }
#
#         except Exception as e:
#             # Handle errors gracefully
#             LOGGER.error(f"Error in sample tool: {str(e)}")
#             return {
#                 "success": False,
#                 "error": f"Tool execution failed: {str(e)}"
#             }
#
#     # Register the tool with the tool manager
#     get_tool_manager().register_backend_tool(
#         sample_tool,                      # Tool definition
#         sample_tool_handler,              # Handler function
#         validate_sample_tool_parameters   # Optional validator function
#     )
#
#     LOGGER.debug("Registered sample backend tool")


# ADVANCED EXAMPLE: Tool with file system access
#
# def register_file_info_tool() -> None:
#     """Example of a backend tool that accesses the file system."""
#
#     file_info_tool = Tool(
#         name="get_file_info",
#         description="Get information about files in the current working directory. Only works on the server.",
#         parameters={
#             "type": "object",
#             "properties": {
#                 "pattern": {
#                     "type": "string",
#                     "description": "File pattern to match (e.g., '*.py', '*.md')",
#                     "default": "*"
#                 },
#                 "include_hidden": {
#                     "type": "boolean",
#                     "description": "Whether to include hidden files",
#                     "default": False
#                 }
#             },
#             "required": []
#         },
#         source="backend",
#         mode=["ask", "chat"]
#     )
#
#     def file_info_handler(arguments: dict[str, Any]) -> dict[str, Any]:
#         """Get file information from the server's file system."""
#         import os
#         import glob
#         from pathlib import Path
#
#         try:
#             pattern = arguments.get("pattern", "*")
#             include_hidden = arguments.get("include_hidden", False)
#
#             # Get current working directory
#             cwd = os.getcwd()
#
#             # Find matching files
#             files = glob.glob(pattern, recursive=False)
#
#             # Filter hidden files if requested
#             if not include_hidden:
#                 files = [f for f in files if not f.startswith('.')]
#
#             # Get file info
#             file_info = []
#             for file_path in files[:20]:  # Limit to 20 files
#                 try:
#                     path = Path(file_path)
#                     stat = path.stat()
#                     file_info.append({
#                         "name": path.name,
#                         "size": stat.st_size,
#                         "is_file": path.is_file(),
#                         "is_dir": path.is_dir(),
#                         "modified": stat.st_mtime
#                     })
#                 except Exception:
#                     continue
#
#             return {
#                 "success": True,
#                 "working_directory": cwd,
#                 "pattern": pattern,
#                 "files_found": len(file_info),
#                 "files": file_info
#             }
#
#         except Exception as e:
#             return {
#                 "success": False,
#                 "error": str(e)
#             }
#
#     get_tool_manager().register_backend_tool(
#         file_info_tool,
#         file_info_handler
#     )


# TO USE THIS SAMPLE TOOL:
#
# 1. Uncomment the code above
# 2. Add this import to __init__.py:
#    from .sample_tool import register_sample_tool
#
# 3. Add this to the __all__ list in __init__.py:
#    __all__ = ["register_server_debug_tool", "register_sample_tool"]
#
# 4. Add this to the register_all_backend_tools() function in __init__.py:
#    def register_all_backend_tools():
#        register_server_debug_tool()
#        register_sample_tool()
#
# 5. Restart the marimo server
#
# The AI will then be able to use your tool in conversations!
