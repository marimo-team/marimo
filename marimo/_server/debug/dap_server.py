# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


class DAPMessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"


class DAPRequestType(Enum):
    INITIALIZE = "initialize"
    ATTACH = "attach"
    SET_BREAKPOINTS = "setBreakpoints"
    CONTINUE = "continue"
    STACK_TRACE = "stackTrace"
    VARIABLES = "variables"
    EVALUATE = "evaluate"
    THREADS = "threads"
    CONFIGURATION_DONE = "configurationDone"
    LAUNCH = "launch"
    DISCONNECT = "disconnect"
    PAUSE = "pause"
    STEP_IN = "stepIn"
    STEP_OUT = "stepOut"
    STEP_OVER = "next"
    SOURCES = "sources"
    SCOPES = "scopes"
    EXCEPTION_INFO = "exceptionInfo"


class DAPEventType(Enum):
    STOPPED = "stopped"
    BREAKPOINT = "breakpoint"


@dataclass
class DAPMessage:
    seq: int
    type: DAPMessageType
    command: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    request_seq: Optional[int] = None
    success: Optional[bool] = None
    message: Optional[str] = None
    body: Optional[Dict[str, Any]] = None
    event: Optional[str] = None


@dataclass
class Breakpoint:
    line: int
    verified: bool = True
    message: Optional[str] = None


@dataclass
class DebugSession:
    session_id: str
    breakpoints: Dict[str, List[Breakpoint]] = None

    def __post_init__(self):
        if self.breakpoints is None:
            self.breakpoints = {}


class DAPTransport(ABC):
    @abstractmethod
    async def start(self, host: str, port: int) -> int:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def send_message(self, message: DAPMessage) -> None:
        pass


class TCPDAPTransport(DAPTransport):
    def __init__(self):
        self.server = None
        self.running = False
        self.clients = []
        self.message_handlers = []
        # Track each client's message format
        self.client_formats = {}  # (reader, writer) -> "http" or "length-prefixed"

    def add_message_handler(self, handler: callable) -> None:
        """Add a message handler."""
        self.message_handlers.append(handler)

    async def start(self, host: str, port: int) -> int:
        """Start the TCP server."""
        self.server = await asyncio.start_server(
            self._handle_client, host, port
        )
        self.running = True
        actual_port = self.server.sockets[0].getsockname()[1]
        LOGGER.info(f"TCP DAP transport started on {host}:{actual_port}")
        return actual_port

    async def stop(self) -> None:
        """Stop the TCP server."""
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for reader, writer in self.clients:
            writer.close()
            await writer.wait_closed()
        self.clients.clear()
        self.client_formats.clear()

    async def send_message(self, message: DAPMessage) -> None:
        """Send a message to all connected clients."""
        # Convert enum fields to strings for JSON serialization
        message_dict = message.__dict__.copy()
        if isinstance(message_dict.get("type"), DAPMessageType):
            message_dict["type"] = message_dict["type"].value

        message_str = json.dumps(message_dict)
        message_bytes = message_str.encode("utf-8")

        LOGGER.info(
            f"Sending DAP response: type={message.type}, command={message.command}, seq={message.seq}"
        )
        LOGGER.debug(f"Response content: {message_str}")

        for reader, writer in self.clients:
            try:
                client_format = self.client_formats.get(
                    (reader, writer), "length-prefixed"
                )

                if client_format == "http":
                    # Send in HTTP-style format
                    header = f"Content-Length: {len(message_bytes)}\r\n\r\n"
                    header_bytes = header.encode("utf-8")
                    writer.write(header_bytes + message_bytes)
                    LOGGER.debug(f"HTTP-style response sent to client")
                else:
                    # Send in length-prefixed format
                    length_bytes = len(message_bytes).to_bytes(4, "big")
                    writer.write(length_bytes + message_bytes)
                    LOGGER.debug(f"Length-prefixed response sent to client")

                await writer.drain()
            except Exception as e:
                LOGGER.error(f"Error sending message to client: {e}")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a new client connection."""
        self.clients.append((reader, writer))
        addr = writer.get_extra_info("peername")
        LOGGER.info(f"New DAP client connected from {addr}")

        try:
            while self.running:
                # Read the first few bytes to see what VS Code is actually sending
                try:
                    first_bytes = await reader.readexactly(
                        20
                    )  # Read first 20 bytes
                    LOGGER.info(
                        f"First 20 bytes from {addr}: {first_bytes} (hex: {first_bytes.hex()})"
                    )
                    LOGGER.info(
                        f"First 20 bytes as string: {first_bytes.decode('utf-8', errors='ignore')}"
                    )

                    # Check if it starts with HTTP headers
                    if first_bytes.startswith(b"Content-Length:"):
                        LOGGER.info(
                            f"Detected HTTP-style DAP transport from {addr}"
                        )
                        self.client_formats[(reader, writer)] = "http"
                        # Read the rest of the HTTP headers and body
                        await self._handle_http_style_messages(
                            reader, writer, addr, first_bytes
                        )
                        # Continue reading more messages
                        continue
                    elif first_bytes.startswith(b"{"):
                        LOGGER.info(f"Detected JSON DAP transport from {addr}")
                        self.client_formats[(reader, writer)] = "json"
                        # Read the rest of the JSON message
                        await self._handle_json_messages(
                            reader, writer, addr, first_bytes
                        )
                        # Continue reading more messages
                        continue
                    else:
                        # Assume length-prefixed format
                        LOGGER.info(
                            f"Detected length-prefixed DAP transport from {addr}"
                        )
                        self.client_formats[(reader, writer)] = (
                            "length-prefixed"
                        )
                        # Try to parse as length-prefixed
                        await self._handle_length_prefixed_messages(
                            reader, writer, addr, first_bytes
                        )
                        # Continue reading more messages
                        continue

                except asyncio.IncompleteReadError:
                    LOGGER.info(
                        f"DAP client {addr} disconnected (IncompleteReadError)"
                    )
                    break
                except Exception as e:
                    LOGGER.error(
                        f"Error determining message format from {addr}: {e}"
                    )
                    break

        except asyncio.IncompleteReadError:
            LOGGER.info(
                f"DAP client {addr} disconnected (IncompleteReadError)"
            )
        except ConnectionResetError:
            LOGGER.info(
                f"DAP client {addr} disconnected (ConnectionResetError)"
            )
        except Exception as e:
            LOGGER.error(f"Error handling DAP client {addr}: {e}")
        finally:
            if (reader, writer) in self.clients:
                self.clients.remove((reader, writer))
            if (reader, writer) in self.client_formats:
                del self.client_formats[(reader, writer)]
            writer.close()
            await writer.wait_closed()
            LOGGER.info(f"DAP client {addr} connection closed")

    async def _handle_http_style_messages(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        addr,
        initial_bytes: bytes,
    ) -> None:
        """Handle HTTP-style DAP messages."""
        LOGGER.info(f"Starting HTTP-style message handling for {addr}")

        # Read the rest of the HTTP headers
        headers = initial_bytes.decode("utf-8", errors="ignore")
        while True:
            line = await reader.readline()
            if not line:
                break
            line_str = line.decode("utf-8", errors="ignore")
            headers += line_str
            LOGGER.info(f"HTTP header: {line_str.strip()}")
            if line_str.strip() == "":
                break

        LOGGER.info(f"Complete HTTP headers: {headers}")

        # Extract Content-Length from headers
        content_length = None
        for line in headers.split("\n"):
            if line.startswith("Content-Length:"):
                content_length = int(line.split(":")[1].strip())
                LOGGER.info(f"Content-Length: {content_length}")
                break

        if content_length is None:
            LOGGER.error("No Content-Length header found")
            return

        # Read the JSON body
        try:
            body_bytes = await reader.readexactly(content_length)
            message_str = body_bytes.decode("utf-8", errors="ignore")
            LOGGER.info(f"HTTP body ({content_length} bytes): {message_str}")

            # Parse and handle the message
            try:
                message_data = json.loads(message_str)
                # Convert string type to enum
                if "type" in message_data and isinstance(
                    message_data["type"], str
                ):
                    message_data["type"] = DAPMessageType(message_data["type"])
                message = DAPMessage(**message_data)
                LOGGER.info(
                    f"Parsed DAP message: type={message.type}, command={message.command}, seq={message.seq}"
                )

                # Call all message handlers
                for handler in self.message_handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        LOGGER.error(f"Error in message handler: {e}")
            except json.JSONDecodeError as e:
                LOGGER.error(f"Failed to parse DAP message: {e}")
                LOGGER.error(f"Raw message was: {message_str}")
                # Try to read more data if the JSON is incomplete
                try:
                    additional_data = await reader.read(
                        1000
                    )  # Read up to 1KB more
                    if additional_data:
                        extended_message = (
                            message_str
                            + additional_data.decode("utf-8", errors="ignore")
                        )
                        LOGGER.info(
                            f"Trying extended message: {extended_message}"
                        )
                        try:
                            message_data = json.loads(extended_message)
                            # Convert string type to enum
                            if "type" in message_data and isinstance(
                                message_data["type"], str
                            ):
                                message_data["type"] = DAPMessageType(
                                    message_data["type"]
                                )
                            message = DAPMessage(**message_data)
                            LOGGER.info(
                                f"Successfully parsed extended DAP message: type={message.type}, command={message.command}, seq={message.seq}"
                            )

                            # Call all message handlers
                            for handler in self.message_handlers:
                                try:
                                    await handler(message)
                                except Exception as e:
                                    LOGGER.error(
                                        f"Error in message handler: {e}"
                                    )
                        except json.JSONDecodeError as e2:
                            LOGGER.error(
                                f"Still failed to parse extended message: {e2}"
                            )
                except Exception as e:
                    LOGGER.error(f"Error reading additional data: {e}")
            except Exception as e:
                LOGGER.error(f"Error reading HTTP body: {e}")
        except Exception as e:
            LOGGER.error(f"Error reading HTTP body: {e}")

    async def _handle_json_messages(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        addr,
        initial_bytes: bytes,
    ) -> None:
        """Handle JSON DAP messages."""
        LOGGER.info(f"Starting JSON message handling for {addr}")

        # Complete the initial JSON message
        message_str = initial_bytes.decode("utf-8", errors="ignore")
        LOGGER.info(f"Initial JSON message: {message_str}")

        # Parse and handle the message
        try:
            message_data = json.loads(message_str)
            # Convert string type to enum
            if "type" in message_data and isinstance(
                message_data["type"], str
            ):
                message_data["type"] = DAPMessageType(message_data["type"])
            message = DAPMessage(**message_data)
            LOGGER.info(
                f"Parsed DAP message: type={message.type}, command={message.command}, seq={message.seq}"
            )

            # Call all message handlers
            for handler in self.message_handlers:
                try:
                    await handler(message)
                except Exception as e:
                    LOGGER.error(f"Error in message handler: {e}")
        except Exception as e:
            LOGGER.error(f"Failed to parse DAP message: {e}")

    async def _handle_length_prefixed_messages(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        addr,
        initial_bytes: bytes,
    ) -> None:
        """Handle length-prefixed DAP messages."""
        LOGGER.info(f"Starting length-prefixed message handling for {addr}")

        # Try to parse the initial bytes as length-prefixed
        try:
            # We already read 20 bytes, so we need to get the length from the first 4
            length_bytes = initial_bytes[:4]
            message_length = int.from_bytes(length_bytes, "big")
            LOGGER.info(f"Message length: {message_length} bytes")

            if message_length > 1000000:  # 1MB limit
                LOGGER.error(
                    f"Message too large ({message_length} bytes), likely malformed"
                )
                return

            # Read the rest of the message
            remaining_length = message_length - (len(initial_bytes) - 4)
            if remaining_length > 0:
                remaining_bytes = await reader.readexactly(remaining_length)
                message_bytes = initial_bytes[4:] + remaining_bytes
            else:
                message_bytes = initial_bytes[4 : 4 + message_length]

            message_str = message_bytes.decode("utf-8", errors="ignore")
            LOGGER.info(f"Raw DAP message: {message_str}")

            # Parse and handle the message
            try:
                message_data = json.loads(message_str)
                # Convert string type to enum
                if "type" in message_data and isinstance(
                    message_data["type"], str
                ):
                    message_data["type"] = DAPMessageType(message_data["type"])
                message = DAPMessage(**message_data)
                LOGGER.info(
                    f"Parsed DAP message: type={message.type}, command={message.command}, seq={message.seq}"
                )

                # Call all message handlers
                for handler in self.message_handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        LOGGER.error(f"Error in message handler: {e}")
            except Exception as e:
                LOGGER.error(f"Failed to parse DAP message: {e}")

        except Exception as e:
            LOGGER.error(f"Error handling length-prefixed message: {e}")


class DAPServer:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self.transport = TCPDAPTransport()
        self.running = False
        self.debug_sessions: Dict[str, DebugSession] = {}
        self.message_seq = 0
        LOGGER.info("DAP server initialized")

    async def start(self, host: str = "localhost", port: int = 5678) -> int:
        """Start the DAP server."""
        LOGGER.info(f"Starting DAP server on {host}:{port}")

        if self.running:
            LOGGER.info("DAP server already running")
            return (
                self.transport.server.sockets[0].getsockname()[1]
                if self.transport.server
                else port
            )

        try:
            # Register message handler
            self.transport.add_message_handler(self._handle_message)
            LOGGER.info("Message handler registered")

            # Start the transport
            actual_port = await self.transport.start(host, port)
            self.running = True
            LOGGER.info(
                f"DAP server started successfully on {host}:{actual_port}"
            )
            return actual_port
        except Exception as e:
            LOGGER.error(f"Failed to start DAP server: {e}")
            raise

    async def stop(self) -> None:
        """Stop the DAP server."""
        if not self.running:
            return

        LOGGER.info("Stopping DAP server")
        self.running = False
        await self.transport.stop()
        LOGGER.info("DAP server stopped")

    async def _handle_message(self, message: DAPMessage) -> None:
        """Handle incoming DAP messages."""
        LOGGER.info(
            f"Processing DAP message: type={message.type}, command={message.command}, seq={message.seq}"
        )

        if message.type == DAPMessageType.REQUEST:
            await self._handle_request(message)
        else:
            LOGGER.warning(f"Unhandled message type: {message.type}")

    async def _handle_request(self, message: DAPMessage) -> None:
        """Handle DAP requests."""
        command = message.command
        if not command:
            LOGGER.warning("Received request with no command")
            return

        LOGGER.info(f"Handling DAP request: {command} (seq={message.seq})")
        if message.arguments:
            LOGGER.debug(f"Request arguments: {message.arguments}")

        try:
            if command == DAPRequestType.INITIALIZE.value:
                await self._handle_initialize(message)
            elif command == DAPRequestType.ATTACH.value:
                await self._handle_attach(message)
            elif command == DAPRequestType.SET_BREAKPOINTS.value:
                await self._handle_set_breakpoints(message)
            elif command == DAPRequestType.CONTINUE.value:
                await self._handle_continue(message)
            elif command == DAPRequestType.STACK_TRACE.value:
                await self._handle_stack_trace(message)
            elif command == DAPRequestType.VARIABLES.value:
                await self._handle_variables(message)
            elif command == DAPRequestType.EVALUATE.value:
                await self._handle_evaluate(message)
            elif command == DAPRequestType.THREADS.value:
                await self._handle_threads(message)
            elif command == DAPRequestType.CONFIGURATION_DONE.value:
                await self._handle_configuration_done(message)
            elif command == DAPRequestType.LAUNCH.value:
                await self._handle_launch(message)
            elif command == DAPRequestType.DISCONNECT.value:
                await self._handle_disconnect(message)
            elif command == DAPRequestType.PAUSE.value:
                await self._handle_pause(message)
            elif command == DAPRequestType.STEP_IN.value:
                await self._handle_step_in(message)
            elif command == DAPRequestType.STEP_OUT.value:
                await self._handle_step_out(message)
            elif command == DAPRequestType.STEP_OVER.value:
                await self._handle_step_over(message)
            elif command == DAPRequestType.SOURCES.value:
                await self._handle_sources(message)
            elif command == DAPRequestType.SCOPES.value:
                await self._handle_scopes(message)
            elif command == DAPRequestType.EXCEPTION_INFO.value:
                await self._handle_exception_info(message)
            else:
                LOGGER.warning(f"Unhandled DAP command: {command}")
                await self._send_error_response(
                    message, f"Unknown command: {command}"
                )
        except Exception as e:
            LOGGER.error(f"Error handling DAP request {command}: {e}")
            await self._send_error_response(message, str(e))

    async def _handle_initialize(self, message: DAPMessage) -> None:
        """Handle initialize request."""
        LOGGER.info("Handling initialize request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={
                "supportsConfigurationDoneRequest": True,
                "supportsEvaluateForHovers": True,
                "supportsSetVariable": True,
                "supportsConditionalBreakpoints": True,
                "supportsHitConditionalBreakpoints": True,
                "supportsLogPoints": True,
                "supportsExceptionInfoRequest": True,
                "supportsExceptionOptions": True,
                "supportsValueFormattingOptions": True,
                "supportsExceptionFilterOptions": True,
                "supportsStepBack": False,
                "supportsSetExpression": True,
                "supportsModulesRequest": True,
                "additionalModuleColumns": [],
                "supportedChecksumAlgorithms": [],
                "supportsRestartRequest": True,
                "supportsGotoTargetsRequest": True,
                "supportsStepInTargetsRequest": True,
                "supportsCompletionsRequest": True,
                "completionTriggerCharacters": [".", "["],
                "supportsModulesRequest": True,
                "supportsRestartFrame": True,
                "supportsStepInTargetsRequest": True,
                "supportsDelayedStackTraceLoading": True,
                "supportsLoadedSourcesRequest": True,
                "supportsLogPoints": True,
                "supportsTerminateThreadsRequest": True,
                "supportsSetExpression": True,
                "supportsTerminateRequest": True,
                "supportsDataBreakpoints": True,
                "supportsReadMemoryRequest": True,
                "supportsWriteMemoryRequest": True,
                "supportsDisassembleRequest": True,
                "supportsCancelRequest": True,
                "supportsBreakpointLocationsRequest": True,
                "supportsClipboardContext": True,
                "supportsSteppingGranularity": True,
                "supportsInstructionBreakpoints": True,
                "supportsExceptionFilterOptions": True,
                "supportsSingleThreadExecutionRequests": True,
            },
        )
        await self.transport.send_message(response)

    async def _handle_attach(self, message: DAPMessage) -> None:
        """Handle attach request."""
        LOGGER.info("Handling attach request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_set_breakpoints(self, message: DAPMessage) -> None:
        """Handle set breakpoints request."""
        LOGGER.info("Handling set breakpoints request")
        args = message.arguments or {}
        source = args.get("source", {})
        path = source.get("path", "")
        breakpoints = args.get("breakpoints", [])

        # Store breakpoints for this file
        session = self._get_default_session()
        if session:
            session.breakpoints[path] = []
            for bp in breakpoints:
                line = bp.get("line", 0)
                session.breakpoints[path].append(Breakpoint(line=line))

        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={
                "breakpoints": [
                    {"id": i, "verified": True, "line": bp.get("line", 0)}
                    for i, bp in enumerate(breakpoints)
                ]
            },
        )
        await self.transport.send_message(response)

    async def _handle_continue(self, message: DAPMessage) -> None:
        """Handle continue request."""
        LOGGER.info("Handling continue request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={"allThreadsContinued": True},
        )
        await self.transport.send_message(response)

    async def _handle_stack_trace(self, message: DAPMessage) -> None:
        """Handle stack trace request."""
        LOGGER.info("Handling stack trace request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={
                "stackFrames": [
                    {
                        "id": 1,
                        "name": "main",
                        "line": 1,
                        "column": 1,
                        "source": {
                            "name": "main.py",
                            "path": "/path/to/main.py",
                        },
                    }
                ],
                "totalFrames": 1,
            },
        )
        await self.transport.send_message(response)

    async def _handle_variables(self, message: DAPMessage) -> None:
        """Handle variables request."""
        LOGGER.info("Handling variables request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={"variables": []},
        )
        await self.transport.send_message(response)

    async def _handle_evaluate(self, message: DAPMessage) -> None:
        """Handle evaluate request."""
        LOGGER.info("Handling evaluate request")
        args = message.arguments or {}
        expression = args.get("expression", "")

        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={
                "result": f"Evaluated: {expression}",
                "type": "string",
                "variablesReference": 0,
            },
        )
        await self.transport.send_message(response)

    async def _handle_threads(self, message: DAPMessage) -> None:
        """Handle threads request."""
        LOGGER.info("Handling threads request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={"threads": [{"id": 1, "name": "MainThread"}]},
        )
        await self.transport.send_message(response)

    async def _handle_configuration_done(self, message: DAPMessage) -> None:
        """Handle configurationDone request."""
        LOGGER.info("Handling configurationDone request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_launch(self, message: DAPMessage) -> None:
        """Handle launch request."""
        LOGGER.info("Handling launch request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_disconnect(self, message: DAPMessage) -> None:
        """Handle disconnect request."""
        LOGGER.info("Handling disconnect request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_pause(self, message: DAPMessage) -> None:
        """Handle pause request."""
        LOGGER.info("Handling pause request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_step_in(self, message: DAPMessage) -> None:
        """Handle stepIn request."""
        LOGGER.info("Handling stepIn request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_step_out(self, message: DAPMessage) -> None:
        """Handle stepOut request."""
        LOGGER.info("Handling stepOut request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_step_over(self, message: DAPMessage) -> None:
        """Handle stepOver request."""
        LOGGER.info("Handling stepOver request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
        )
        await self.transport.send_message(response)

    async def _handle_sources(self, message: DAPMessage) -> None:
        """Handle sources request."""
        LOGGER.info("Handling sources request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={
                "sources": [
                    {
                        "name": "main.py",
                        "path": "/path/to/main.py",
                        "sourceReference": 0,
                    }
                ]
            },
        )
        await self.transport.send_message(response)

    async def _handle_scopes(self, message: DAPMessage) -> None:
        """Handle scopes request."""
        LOGGER.info("Handling scopes request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={
                "scopes": [
                    {
                        "name": "Local",
                        "variablesReference": 0,
                        "expensive": False,
                    }
                ]
            },
        )
        await self.transport.send_message(response)

    async def _handle_exception_info(self, message: DAPMessage) -> None:
        """Handle exceptionInfo request."""
        LOGGER.info("Handling exceptionInfo request")
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=message.seq,
            success=True,
            command=message.command,
            body={
                "exceptionId": "unhandled",
                "description": "An unhandled exception occurred.",
                "breakMode": "always",
            },
        )
        await self.transport.send_message(response)

    async def _send_error_response(
        self, original_message: DAPMessage, error_message: str
    ) -> None:
        """Send an error response."""
        response = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.RESPONSE,
            request_seq=original_message.seq,
            success=False,
            command=original_message.command,
            message=error_message,
        )
        await self.transport.send_message(response)

    def _next_seq(self) -> int:
        """Get the next sequence number."""
        self.message_seq += 1
        return self.message_seq

    def _get_default_session(self) -> Optional[DebugSession]:
        """Get the default debug session."""
        if not self.debug_sessions:
            session_id = "default"
            self.debug_sessions[session_id] = DebugSession(
                session_id=session_id
            )
        return self.debug_sessions.get("default")

    def _get_debug_session(self, session_id: str) -> Optional[DebugSession]:
        """Get a debug session by ID."""
        return self.debug_sessions.get(session_id)

    def _path_to_cell_id(self, path: str) -> Optional[str]:
        """Convert a file path to a cell ID."""
        # This is a placeholder - in a real implementation,
        # you'd map file paths to cell IDs
        return None

    def install_breakpoint_hook(self) -> None:
        """Install a breakpoint hook for PDB integration."""
        # This is a placeholder for PDB integration
        pass

    async def _send_stopped_event(self, reason: str = "breakpoint") -> None:
        """Send a stopped event."""
        event = DAPMessage(
            seq=self._next_seq(),
            type=DAPMessageType.EVENT,
            event=DAPEventType.STOPPED.value,
            body={"reason": reason, "threadId": 1, "allThreadsStopped": True},
        )
        await self.transport.send_message(event)


# Global DAP server instance
_dap_server: Optional[DAPServer] = None


def get_dap_server(session_manager) -> DAPServer:
    """Get the global DAP server instance."""
    global _dap_server
    if _dap_server is None:
        LOGGER.info("Creating new DAP server instance")
        _dap_server = DAPServer(session_manager)
    return _dap_server
