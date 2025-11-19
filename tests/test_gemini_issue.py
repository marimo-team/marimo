"""Test script to reproduce Gemini validation error with tool parameters issue #7186"""

from dataclasses import dataclass
from typing import Literal, Union

from marimo._ai._convert import convert_to_google_tools
from marimo._ai._tools.base import ToolContext, ToolBase
from marimo._server.ai.tools.types import ToolDefinition


@dataclass
class TestArgs:
    """Test arguments with Union types that might cause issues."""
    action: Union[Literal["add"], Literal["update"], Literal["delete"]]
    value: str


@dataclass
class TestOutput:
    """Test output."""
    result: str


class TestTool(ToolBase[TestArgs, TestOutput]):
    """Test tool to reproduce the issue."""
    
    def handle(self, args: TestArgs) -> TestOutput:
        return TestOutput(result=f"Executed {args.action} with {args.value}")


def main():
    # Create a mock context
    context = ToolContext(app=None)  # type: ignore
    tool = TestTool(context)
    
    # Get the backend tool definition
    tool_definition, _ = tool.as_backend_tool(mode=["ask"])
    
    print("Tool Definition:")
    print(f"Name: {tool_definition.name}")
    print(f"Description: {tool_definition.description}")
    print(f"\nParameters (raw):")
    import json
    print(json.dumps(tool_definition.parameters, indent=2))
    
    # Convert to Google format
    google_tools = convert_to_google_tools([tool_definition])
    
    print("\n\nGoogle Tools Format:")
    print(json.dumps(google_tools, indent=2))
    
    # Check for problematic fields
    print("\n\nChecking for problematic fields:")
    params_str = json.dumps(google_tools)
    if "anyOf" in params_str:
        print("WARNING: Found 'anyOf' in parameters")
    if "const" in params_str:
        print("WARNING: Found 'const' in parameters")
    if "oneOf" in params_str:
        print("WARNING: Found 'oneOf' in parameters")
    

if __name__ == "__main__":
    main()
