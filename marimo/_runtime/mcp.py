from __future__ import annotations

from marimo._mcp import registry
from marimo._runtime.requests import MCPEvaluationRequest, MCPMessage
from marimo._server.types import QueueType


def mcp_worker(
    mcp_message_queue: QueueType[MCPMessage | MCPEvaluationRequest],
) -> None:
    """MCP worker that processes evaluation requests.

    Args:
        mcp_evaluation_queue: Queue from which evaluation requests are pulled
        mcp_message_queue: Queue for MCP messages
    """
    while True:
        message = mcp_message_queue.get()
        # TODO: get proper server name
        server = registry.get_server("local")
        if isinstance(message, MCPEvaluationRequest):
            pass
        elif isinstance(message, MCPMessage):
            print(message)
            if message.mcp_message.message == "resources/list":
                print(server.resources)
            elif message.mcp_message.message == "tools/list":
                print(server.tools)
            elif message.mcp_message.message == "prompts/list":
                print(server.prompts)
            else:
                print("Unknown message")
