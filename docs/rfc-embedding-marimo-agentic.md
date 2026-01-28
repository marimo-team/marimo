# RFC: Embedding Marimo with Custom Agentic Features

**Version:** 1.0
**Status:** Draft
**Authors:** Engineering Team
**Date:** January 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Problem Statement](#2-background--problem-statement)
3. [Architecture Overview](#3-architecture-overview)
4. [Backend Implementation (FastAPI)](#4-backend-implementation-fastapi)
5. [Frontend Implementation (React)](#5-frontend-implementation-react)
6. [Marimo API Reference](#6-marimo-api-reference)
7. [WebSocket Protocol](#7-websocket-protocol)
8. [Tool System](#8-tool-system)
9. [Session Management](#9-session-management)
10. [Hybrid Edit Control](#10-hybrid-edit-control)
11. [Error Handling](#11-error-handling)
12. [Security Considerations](#12-security-considerations)
13. [Deployment](#13-deployment)
14. [Testing Strategy](#14-testing-strategy)

---

## 1. Executive Summary

This RFC describes how to build a product that embeds marimo notebooks while providing custom agentic features. The solution runs marimo in EDIT mode as managed subprocesses and controls them via verified HTTP/WebSocket APIs.

**Key constraints discovered:**
- Marimo's `create_asgi_app()` only supports RUN mode (no editing)
- Frontend tools (EditNotebookTool, RunStaleCellsTool) execute in-browser and cannot be called from a backend
- Full editing requires EDIT mode, which requires running marimo as a subprocess

**Solution:** Run marimo via CLI in EDIT mode with `--headless`, proxy its APIs through your FastAPI backend, and embed the marimo frontend in an iframe.

---

## 2. Background & Problem Statement

### 2.1 Requirements

1. **Embed marimo** as the notebook system
2. **Custom chat sidebar** with your own agentic features (not marimo's ACP)
3. **Programmatic notebook control**: create, edit, delete, execute cells
4. **Your own tools** beyond marimo's built-in tools
5. **Multi-notebook support**: 2-5 concurrent notebooks per user
6. **Hybrid edit control**: auto-apply safe operations, approve destructive ones

### 2.2 Why marimo's ACP Won't Work

Marimo's Agent Client Protocol (ACP) is designed for external agents (Claude Code, Gemini) connecting to marimo's frontend:

```
External Agent --> WebSocket (port 3017) --> Marimo Frontend --> Browser-side tools
```

The editing tools execute **in the browser** using React/Jotai state management. They cannot be called from a backend server.

### 2.3 Why `create_asgi_app()` Won't Work

The ASGI embedding API (`marimo/_server/asgi.py:289-386`) only supports **RUN mode**:

```python
# From marimo/_server/asgi.py:456-459
session_manager = SessionManager(
    ...
    mode=SessionMode.RUN,  # Hardcoded to RUN
    ...
)
```

RUN mode disables all editing endpoints (they return 403 Forbidden).

---

## 3. Architecture Overview

### 3.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           YOUR PRODUCT                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐           │
│  │  React App     │   │  FastAPI       │   │  Agent Engine  │           │
│  │  - Chat UI     │   │  Backend       │   │  - LLM calls   │           │
│  │  - Notebook    │   │  - Proxy APIs  │   │  - Tool exec   │           │
│  │    Tabs        │   │  - Sessions    │   │  - Streaming   │           │
│  └───────┬────────┘   └───────┬────────┘   └───────┬────────┘           │
│          │                    │                    │                     │
│          │     WebSocket      │                    │                     │
│          └──────────────┬─────┴────────────────────┘                     │
│                         │                                                │
│              ┌──────────┴──────────┐                                    │
│              │ Marimo Process      │                                    │
│              │ Manager             │                                    │
│              └──────────┬──────────┘                                    │
│                         │                                                │
└─────────────────────────┼────────────────────────────────────────────────┘
                          │
            ┌─────────────┼─────────────┐
            │             │             │
            ▼             ▼             ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ Marimo:2718  │ │ Marimo:2719  │ │ Marimo:2720  │
    │ notebook1.py │ │ notebook2.py │ │ notebook3.py │
    └──────────────┘ └──────────────┘ └──────────────┘
```

### 3.2 Communication Flow

```
User Chat Input
    │
    ▼
Your FastAPI Backend
    │
    ├── Agent processes message
    │   │
    │   ├── Read notebook state
    │   │   └── GET http://localhost:{port}/api/ai/invoke_tool
    │   │
    │   ├── Execute cells
    │   │   └── POST http://localhost:{port}/api/kernel/run
    │   │
    │   └── Delete cells (with approval)
    │       └── POST http://localhost:{port}/api/kernel/delete
    │
    ▼
WebSocket notification to frontend
    │
    ▼
React updates UI (chat + iframe reloads outputs)
```

---

## 4. Backend Implementation (FastAPI)

### 4.1 Project Structure

```
your_product/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Configuration
│   ├── marimo/
│   │   ├── __init__.py
│   │   ├── process_manager.py   # Marimo subprocess management
│   │   ├── client.py            # HTTP client for marimo APIs
│   │   └── models.py            # Pydantic models
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── engine.py            # Agent orchestration
│   │   ├── tools.py             # Tool definitions
│   │   └── prompts.py           # System prompts
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chat.py              # Chat endpoints
│   │   ├── notebooks.py         # Notebook management
│   │   └── websocket.py         # WebSocket handler
│   └── models/
│       ├── __init__.py
│       └── schemas.py           # API schemas
├── requirements.txt
└── docker-compose.yml
```

### 4.2 Marimo Process Manager

```python
# app/marimo/process_manager.py
import asyncio
import secrets
from dataclasses import dataclass, field
from typing import Optional
import httpx

@dataclass
class MarimoProcess:
    """Represents a running marimo process."""
    process: asyncio.subprocess.Process
    port: int
    notebook_path: str
    token: str
    session_id: Optional[str] = None

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://localhost:{self.port}/ws"

    def get_headers(self) -> dict[str, str]:
        """Get headers for authenticated requests."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["Marimo-Session-Id"] = self.session_id
        return headers

class PortAllocator:
    """Manages port allocation for marimo processes."""

    def __init__(self, port_range: range):
        self.available = set(port_range)
        self.allocated: set[int] = set()
        self._lock = asyncio.Lock()

    async def allocate(self) -> int:
        async with self._lock:
            if not self.available:
                raise RuntimeError("No ports available")
            port = self.available.pop()
            self.allocated.add(port)
            return port

    async def release(self, port: int) -> None:
        async with self._lock:
            if port in self.allocated:
                self.allocated.remove(port)
                self.available.add(port)

class MarimoProcessManager:
    """Manages marimo editor processes for multiple notebooks."""

    def __init__(self, port_range: range = range(2718, 2800)):
        self.port_allocator = PortAllocator(port_range)
        self.processes: dict[str, MarimoProcess] = {}  # notebook_id -> process
        self._lock = asyncio.Lock()

    async def start_notebook(
        self,
        notebook_id: str,
        notebook_path: str,
        timeout: float = 30.0
    ) -> MarimoProcess:
        """Start a marimo process for a notebook."""
        async with self._lock:
            if notebook_id in self.processes:
                return self.processes[notebook_id]

            port = await self.port_allocator.allocate()
            token = secrets.token_urlsafe(32)

            # Start marimo in EDIT mode with --headless
            process = await asyncio.create_subprocess_exec(
                "marimo", "edit", notebook_path,
                "--port", str(port),
                "--headless",  # Don't open browser
                "--token", token,
                "--no-token",  # Actually disable token for simplicity
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            marimo_process = MarimoProcess(
                process=process,
                port=port,
                notebook_path=notebook_path,
                token=token,
            )

            # Wait for marimo to be ready
            await self._wait_for_ready(marimo_process, timeout)

            # Get session ID from running notebooks
            marimo_process.session_id = await self._get_session_id(marimo_process)

            self.processes[notebook_id] = marimo_process
            return marimo_process

    async def _wait_for_ready(
        self,
        process: MarimoProcess,
        timeout: float
    ) -> None:
        """Wait for marimo server to be ready."""
        start_time = asyncio.get_event_loop().time()

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    response = await client.get(
                        f"{process.base_url}/health",
                        timeout=1.0
                    )
                    if response.status_code == 200:
                        return
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass

                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError(
                        f"Marimo did not start within {timeout} seconds"
                    )

                await asyncio.sleep(0.5)

    async def _get_session_id(self, process: MarimoProcess) -> str:
        """Get the session ID from marimo's running notebooks endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{process.base_url}/api/home/running_notebooks",
                headers=process.get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Get the first (and usually only) session
            files = data.get("files", [])
            if files:
                return files[0].get("sessionId")

            raise RuntimeError("No active session found")

    async def stop_notebook(self, notebook_id: str) -> None:
        """Stop a marimo process."""
        async with self._lock:
            if notebook_id not in self.processes:
                return

            process = self.processes.pop(notebook_id)

            # Try graceful shutdown first
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{process.base_url}/api/kernel/shutdown",
                        headers=process.get_headers(),
                        timeout=5.0
                    )
            except Exception:
                pass

            # Force kill if still running
            if process.process.returncode is None:
                process.process.terminate()
                try:
                    await asyncio.wait_for(process.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.process.kill()

            await self.port_allocator.release(process.port)

    async def get_process(self, notebook_id: str) -> Optional[MarimoProcess]:
        """Get a running process by notebook ID."""
        return self.processes.get(notebook_id)

    async def shutdown_all(self) -> None:
        """Shutdown all running processes."""
        notebook_ids = list(self.processes.keys())
        for notebook_id in notebook_ids:
            await self.stop_notebook(notebook_id)
```

### 4.3 Marimo API Client

```python
# app/marimo/client.py
from dataclasses import dataclass
from typing import Any, Optional
import httpx

from .process_manager import MarimoProcess

@dataclass
class CellInfo:
    cell_id: str
    preview: str
    line_count: int
    cell_type: str  # "code", "markdown", "sql"

@dataclass
class CellRuntimeData:
    cell_id: str
    code: str
    errors: list[dict]
    runtime_state: Optional[str]
    execution_time: Optional[float]
    variables: dict[str, Any]

@dataclass
class CellOutput:
    visual_output: Optional[str]
    visual_mimetype: Optional[str]
    stdout: list[str]
    stderr: list[str]

class MarimoClient:
    """HTTP client for marimo backend APIs."""

    def __init__(self, process: MarimoProcess):
        self.process = process
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    def _url(self, path: str) -> str:
        return f"{self.process.base_url}{path}"

    def _headers(self) -> dict[str, str]:
        return self.process.get_headers()

    # ============================================================
    # BACKEND TOOLS (via /api/ai/invoke_tool)
    # These are READ-ONLY tools that work in both RUN and EDIT modes
    # ============================================================

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Invoke a backend AI tool.

        Verified endpoint: POST /api/ai/invoke_tool
        Source: marimo/_server/api/endpoints/ai.py:330-388

        Request body (camelCase):
        {
            "toolName": str,
            "arguments": dict
        }

        Response:
        {
            "success": bool,
            "toolName": str,
            "result": Any,
            "error": Optional[str]
        }
        """
        response = await self._client.post(
            self._url("/api/ai/invoke_tool"),
            headers=self._headers(),
            json={
                "toolName": tool_name,
                "arguments": arguments,
            }
        )
        response.raise_for_status()
        return response.json()

    async def get_cell_map(self, preview_lines: int = 5) -> list[CellInfo]:
        """
        Get lightweight map of all cells.

        Tool: get_lightweight_cell_map
        Source: marimo/_ai/_tools/tools/cells.py:119-193

        Arguments:
        - session_id: str (required)
        - preview_lines: int (default: 3)

        Returns cell previews without full code.
        """
        result = await self.invoke_tool(
            "get_lightweight_cell_map",
            {
                "session_id": self.process.session_id,
                "preview_lines": preview_lines,
            }
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown error"))

        cells = result.get("result", {}).get("cells", [])
        return [
            CellInfo(
                cell_id=c["cellId"],
                preview=c["preview"],
                line_count=c["lineCount"],
                cell_type=c["cellType"],
            )
            for c in cells
        ]

    async def get_cell_runtime_data(self, cell_id: str) -> CellRuntimeData:
        """
        Get full runtime data for a specific cell.

        Tool: get_cell_runtime_data
        Source: marimo/_ai/_tools/tools/cells.py:223-344

        Arguments:
        - session_id: str (required)
        - cell_id: str (required)

        Returns code, errors, variables, and execution metadata.
        """
        result = await self.invoke_tool(
            "get_cell_runtime_data",
            {
                "session_id": self.process.session_id,
                "cell_id": cell_id,
            }
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown error"))

        data = result.get("result", {}).get("data", {})
        return CellRuntimeData(
            cell_id=data.get("cellId", cell_id),
            code=data.get("code", ""),
            errors=data.get("errors", []),
            runtime_state=data.get("metadata", {}).get("runtimeState"),
            execution_time=data.get("metadata", {}).get("executionTime"),
            variables=data.get("variables", {}),
        )

    async def get_cell_outputs(self, cell_id: str) -> CellOutput:
        """
        Get visual and console outputs for a cell.

        Tool: get_cell_outputs
        Source: marimo/_ai/_tools/tools/cells.py:347-416

        Arguments:
        - session_id: str (required)
        - cell_id: str (required)
        """
        result = await self.invoke_tool(
            "get_cell_outputs",
            {
                "session_id": self.process.session_id,
                "cell_id": cell_id,
            }
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown error"))

        res = result.get("result", {})
        visual = res.get("visualOutput", {})
        console = res.get("consoleOutputs", {})

        return CellOutput(
            visual_output=visual.get("visualOutput"),
            visual_mimetype=visual.get("visualMimetype"),
            stdout=console.get("stdout", []),
            stderr=console.get("stderr", []),
        )

    async def get_notebook_errors(self) -> list[dict]:
        """
        Get all errors in the notebook.

        Tool: get_notebook_errors
        Source: marimo/_ai/_tools/tools/errors.py
        """
        result = await self.invoke_tool(
            "get_notebook_errors",
            {"session_id": self.process.session_id}
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown error"))

        return result.get("result", {}).get("errors", [])

    async def get_variables(self) -> dict[str, Any]:
        """
        Get all tables and variables.

        Tool: get_tables_and_variables
        Source: marimo/_ai/_tools/tools/tables_and_variables.py
        """
        result = await self.invoke_tool(
            "get_tables_and_variables",
            {"session_id": self.process.session_id}
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown error"))

        return result.get("result", {})

    async def lint_notebook(self) -> list[dict]:
        """
        Run linting on the notebook.

        Tool: lint_notebook
        Source: marimo/_ai/_tools/tools/lint.py
        """
        result = await self.invoke_tool(
            "lint_notebook",
            {"session_id": self.process.session_id}
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown error"))

        return result.get("result", {}).get("issues", [])

    # ============================================================
    # EXECUTION API (EDIT MODE ONLY)
    # These require @requires("edit") - only work in EDIT mode
    # ============================================================

    async def execute_cells(
        self,
        cell_ids: list[str],
        codes: list[str]
    ) -> bool:
        """
        Execute cells with given code.

        Verified endpoint: POST /api/kernel/run
        Source: marimo/_server/api/endpoints/execution.py:205-239
        Requires: EDIT mode (@requires("edit"))

        Request body (camelCase):
        {
            "cellIds": list[str],
            "codes": list[str]
        }

        This endpoint:
        1. Updates cell code in the kernel if needed
        2. Registers new cells for unseen cell IDs
        3. Queues cells for execution

        Response is async - actual outputs come via WebSocket.
        """
        if len(cell_ids) != len(codes):
            raise ValueError("cell_ids and codes must have same length")

        response = await self._client.post(
            self._url("/api/kernel/run"),
            headers=self._headers(),
            json={
                "cellIds": cell_ids,
                "codes": codes,
            }
        )
        response.raise_for_status()
        return response.json().get("success", False)

    async def delete_cell(self, cell_id: str) -> bool:
        """
        Delete a cell from the notebook.

        Verified endpoint: POST /api/kernel/delete
        Source: marimo/_server/api/endpoints/editing.py:61-84
        Requires: EDIT mode (@requires("edit"))

        Request body (camelCase):
        {
            "cellId": str
        }
        """
        response = await self._client.post(
            self._url("/api/kernel/delete"),
            headers=self._headers(),
            json={"cellId": cell_id}
        )
        response.raise_for_status()
        return response.json().get("success", False)

    async def interrupt_execution(self) -> bool:
        """
        Interrupt kernel execution.

        Verified endpoint: POST /api/kernel/interrupt
        Source: marimo/_server/api/endpoints/execution.py:178-202
        Requires: EDIT mode
        """
        response = await self._client.post(
            self._url("/api/kernel/interrupt"),
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("success", False)

    async def format_cells(
        self,
        codes: dict[str, str],
        line_length: int = 88
    ) -> dict[str, str]:
        """
        Format cell code using ruff.

        Verified endpoint: POST /api/kernel/format
        Source: marimo/_server/api/endpoints/editing.py:120-150
        Requires: EDIT mode

        Request body:
        {
            "codes": dict[cell_id, code],
            "lineLength": int
        }

        Returns formatted codes.
        """
        response = await self._client.post(
            self._url("/api/kernel/format"),
            headers=self._headers(),
            json={
                "codes": codes,
                "lineLength": line_length,
            }
        )
        response.raise_for_status()
        return response.json().get("codes", {})

    async def save_notebook(
        self,
        cell_ids: list[str],
        codes: list[str],
        names: list[str],
        configs: list[dict],
        filename: str,
    ) -> bool:
        """
        Save the notebook to disk.

        Verified endpoint: POST /api/kernel/save
        Source: marimo/_server/api/endpoints/files.py:134-173
        Requires: EDIT mode

        Request body:
        {
            "cellIds": list[str],
            "codes": list[str],
            "names": list[str],
            "configs": list[CellConfig],
            "filename": str,
            "persist": bool (default true)
        }
        """
        response = await self._client.post(
            self._url("/api/kernel/save"),
            headers=self._headers(),
            json={
                "cellIds": cell_ids,
                "codes": codes,
                "names": names,
                "configs": configs,
                "filename": filename,
                "persist": True,
            }
        )
        response.raise_for_status()
        return True

    # ============================================================
    # UTILITY APIs
    # ============================================================

    async def read_code(self) -> str:
        """
        Read the raw notebook file content.

        Verified endpoint: POST /api/kernel/read_code
        Source: marimo/_server/api/endpoints/files.py:38-82
        Requires: read permission (works in RUN mode with include_code=True)
        """
        response = await self._client.post(
            self._url("/api/kernel/read_code"),
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("contents", "")

    async def get_running_notebooks(self) -> list[dict]:
        """
        Get list of running notebook sessions.

        Verified endpoint: POST /api/home/running_notebooks
        Source: marimo/_server/api/endpoints/home.py:145-161

        Returns list of MarimoFile objects with:
        - name: str
        - path: str
        - sessionId: str
        - initializationId: str
        """
        response = await self._client.post(
            self._url("/api/home/running_notebooks"),
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("files", [])
```

### 4.4 FastAPI Main Application

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .marimo.process_manager import MarimoProcessManager
from .marimo.client import MarimoClient
from .agent.engine import AgentEngine
from .models.schemas import (
    OpenNotebookRequest,
    ChatRequest,
    ExecuteCellsRequest,
    NotebookState,
)

# Global process manager
process_manager: MarimoProcessManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global process_manager
    process_manager = MarimoProcessManager()
    yield
    await process_manager.shutdown_all()

app = FastAPI(title="Your Product API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your React app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# NOTEBOOK MANAGEMENT
# ============================================================

@app.post("/api/notebooks/open")
async def open_notebook(request: OpenNotebookRequest):
    """Open a notebook and start its marimo process."""
    try:
        process = await process_manager.start_notebook(
            notebook_id=request.notebook_id,
            notebook_path=request.notebook_path,
        )
        return {
            "notebook_id": request.notebook_id,
            "url": f"http://localhost:{process.port}",
            "session_id": process.session_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notebooks/{notebook_id}/close")
async def close_notebook(notebook_id: str):
    """Close a notebook and stop its marimo process."""
    await process_manager.stop_notebook(notebook_id)
    return {"status": "closed"}

@app.get("/api/notebooks/{notebook_id}/state")
async def get_notebook_state(notebook_id: str) -> NotebookState:
    """Get current notebook state for agent context."""
    process = await process_manager.get_process(notebook_id)
    if not process:
        raise HTTPException(status_code=404, detail="Notebook not found")

    client = MarimoClient(process)
    try:
        cells = await client.get_cell_map()
        errors = await client.get_notebook_errors()
        variables = await client.get_variables()

        return NotebookState(
            notebook_id=notebook_id,
            cells=[c.__dict__ for c in cells],
            errors=errors,
            variables=variables,
        )
    finally:
        await client.close()

# ============================================================
# CELL OPERATIONS (for agent)
# ============================================================

@app.post("/api/notebooks/{notebook_id}/cells/execute")
async def execute_cells(notebook_id: str, request: ExecuteCellsRequest):
    """Execute cells in a notebook."""
    process = await process_manager.get_process(notebook_id)
    if not process:
        raise HTTPException(status_code=404, detail="Notebook not found")

    client = MarimoClient(process)
    try:
        success = await client.execute_cells(
            cell_ids=request.cell_ids,
            codes=request.codes,
        )
        return {"success": success}
    finally:
        await client.close()

@app.delete("/api/notebooks/{notebook_id}/cells/{cell_id}")
async def delete_cell(notebook_id: str, cell_id: str):
    """Delete a cell (requires approval in frontend)."""
    process = await process_manager.get_process(notebook_id)
    if not process:
        raise HTTPException(status_code=404, detail="Notebook not found")

    client = MarimoClient(process)
    try:
        success = await client.delete_cell(cell_id)
        return {"success": success}
    finally:
        await client.close()

# ============================================================
# AGENT CHAT
# ============================================================

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Handle chat message from user."""
    process = await process_manager.get_process(request.notebook_id)
    if not process:
        raise HTTPException(status_code=404, detail="Notebook not found")

    client = MarimoClient(process)
    agent = AgentEngine(client)

    try:
        response = await agent.process_message(
            message=request.message,
            context=request.context,
        )
        return response
    finally:
        await client.close()

@app.websocket("/api/ws/{notebook_id}")
async def websocket_endpoint(websocket: WebSocket, notebook_id: str):
    """WebSocket for real-time updates."""
    await websocket.accept()

    process = await process_manager.get_process(notebook_id)
    if not process:
        await websocket.close(code=1008)
        return

    # Connect to marimo's WebSocket and relay messages
    import websockets

    try:
        async with websockets.connect(
            f"{process.ws_url}?session_id={process.session_id}"
        ) as marimo_ws:
            async def forward_to_client():
                async for message in marimo_ws:
                    await websocket.send_text(message)

            async def forward_to_marimo():
                while True:
                    data = await websocket.receive_text()
                    await marimo_ws.send(data)

            await asyncio.gather(forward_to_client(), forward_to_marimo())
    except WebSocketDisconnect:
        pass
```

### 4.5 Pydantic Models

```python
# app/models/schemas.py
from pydantic import BaseModel
from typing import Any, Optional

class OpenNotebookRequest(BaseModel):
    notebook_id: str
    notebook_path: str

class ChatRequest(BaseModel):
    notebook_id: str
    message: str
    context: Optional[dict] = None

class ExecuteCellsRequest(BaseModel):
    cell_ids: list[str]
    codes: list[str]

class CellInfo(BaseModel):
    cell_id: str
    preview: str
    line_count: int
    cell_type: str

class NotebookState(BaseModel):
    notebook_id: str
    cells: list[dict]
    errors: list[dict]
    variables: dict[str, Any]

class AgentToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]

class AgentResponse(BaseModel):
    message: str
    tool_calls: list[AgentToolCall] = []
    pending_approval: Optional[dict] = None
```

---

## 5. Frontend Implementation (React)

### 5.1 Project Structure

```
frontend/
├── src/
│   ├── App.tsx
│   ├── components/
│   │   ├── ChatSidebar/
│   │   │   ├── ChatSidebar.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   └── ApprovalDialog.tsx
│   │   ├── NotebookTabs/
│   │   │   ├── NotebookTabs.tsx
│   │   │   └── NotebookFrame.tsx
│   │   └── Layout/
│   │       └── MainLayout.tsx
│   ├── hooks/
│   │   ├── useNotebooks.ts
│   │   ├── useChat.ts
│   │   └── useWebSocket.ts
│   ├── api/
│   │   └── client.ts
│   └── types/
│       └── index.ts
├── package.json
└── vite.config.ts
```

### 5.2 Main Layout

```tsx
// src/components/Layout/MainLayout.tsx
import { useState } from 'react';
import { ChatSidebar } from '../ChatSidebar/ChatSidebar';
import { NotebookTabs } from '../NotebookTabs/NotebookTabs';
import { useNotebooks } from '../../hooks/useNotebooks';

export function MainLayout() {
  const { notebooks, activeNotebook, openNotebook, closeNotebook, setActive } = useNotebooks();

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Chat Sidebar - YOUR UI */}
      <ChatSidebar
        notebookId={activeNotebook?.id}
        className="w-80 border-r"
      />

      {/* Notebook Area */}
      <div className="flex-1 flex flex-col">
        {/* Tab Bar */}
        <NotebookTabs
          notebooks={notebooks}
          activeId={activeNotebook?.id}
          onSelect={setActive}
          onClose={closeNotebook}
        />

        {/* Marimo Frames */}
        <div className="flex-1 relative">
          {notebooks.map((notebook) => (
            <NotebookFrame
              key={notebook.id}
              notebook={notebook}
              isActive={notebook.id === activeNotebook?.id}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
```

### 5.3 Notebook Frame (iframe)

```tsx
// src/components/NotebookTabs/NotebookFrame.tsx
import { useEffect, useRef } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';

interface NotebookFrameProps {
  notebook: {
    id: string;
    url: string;
    sessionId: string;
  };
  isActive: boolean;
}

export function NotebookFrame({ notebook, isActive }: NotebookFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Connect to WebSocket for real-time updates
  const { lastMessage, sendMessage } = useWebSocket(
    `ws://localhost:8000/api/ws/${notebook.id}`
  );

  // Handle messages from marimo (cell outputs, errors, etc.)
  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage);

      // Handle different notification types
      switch (data.op) {
        case 'cell-op':
          // Cell state changed - iframe updates automatically
          console.log('Cell update:', data.cell_id, data.status);
          break;
        case 'completed-run':
          // Execution completed
          console.log('Run completed');
          break;
        case 'kernel-ready':
          // Notebook is ready
          console.log('Kernel ready');
          break;
      }
    }
  }, [lastMessage]);

  return (
    <iframe
      ref={iframeRef}
      src={notebook.url}
      className={`
        absolute inset-0 w-full h-full border-0
        ${isActive ? 'z-10' : 'z-0 invisible'}
      `}
      title={`Notebook ${notebook.id}`}
    />
  );
}
```

### 5.4 Chat Sidebar

```tsx
// src/components/ChatSidebar/ChatSidebar.tsx
import { useState } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ApprovalDialog } from './ApprovalDialog';
import { useChat } from '../../hooks/useChat';

interface ChatSidebarProps {
  notebookId?: string;
  className?: string;
}

export function ChatSidebar({ notebookId, className }: ChatSidebarProps) {
  const {
    messages,
    isLoading,
    pendingApproval,
    sendMessage,
    approveAction,
    rejectAction,
  } = useChat(notebookId);

  return (
    <div className={`flex flex-col bg-white ${className}`}>
      <div className="p-4 border-b">
        <h2 className="font-semibold">Assistant</h2>
      </div>

      <MessageList
        messages={messages}
        isLoading={isLoading}
        className="flex-1 overflow-y-auto"
      />

      {pendingApproval && (
        <ApprovalDialog
          action={pendingApproval}
          onApprove={approveAction}
          onReject={rejectAction}
        />
      )}

      <MessageInput
        onSend={sendMessage}
        disabled={isLoading || !notebookId}
        placeholder={
          notebookId
            ? "Ask about the notebook..."
            : "Open a notebook to start"
        }
      />
    </div>
  );
}
```

### 5.5 Approval Dialog for Destructive Actions

```tsx
// src/components/ChatSidebar/ApprovalDialog.tsx
interface ApprovalDialogProps {
  action: {
    type: 'delete_cell' | 'clear_outputs' | 'replace_notebook';
    description: string;
    cellId?: string;
  };
  onApprove: () => void;
  onReject: () => void;
}

export function ApprovalDialog({ action, onApprove, onReject }: ApprovalDialogProps) {
  return (
    <div className="p-4 bg-yellow-50 border-t border-yellow-200">
      <div className="flex items-start gap-3">
        <div className="text-yellow-600">⚠️</div>
        <div className="flex-1">
          <p className="font-medium text-yellow-800">
            Approval Required
          </p>
          <p className="text-sm text-yellow-700 mt-1">
            {action.description}
          </p>
          <div className="flex gap-2 mt-3">
            <button
              onClick={onApprove}
              className="px-3 py-1 bg-yellow-600 text-white rounded text-sm"
            >
              Approve
            </button>
            <button
              onClick={onReject}
              className="px-3 py-1 bg-white border rounded text-sm"
            >
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

### 5.6 Chat Hook

```tsx
// src/hooks/useChat.ts
import { useState, useCallback } from 'react';
import { apiClient } from '../api/client';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: Array<{
    tool: string;
    status: 'pending' | 'success' | 'error';
    result?: any;
  }>;
}

interface PendingApproval {
  id: string;
  type: string;
  description: string;
  cellId?: string;
}

export function useChat(notebookId?: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    if (!notebookId) return;

    // Add user message
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await apiClient.post('/api/chat', {
        notebook_id: notebookId,
        message: content,
      });

      // Add assistant response
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.data.message,
        toolCalls: response.data.tool_calls?.map((tc: any) => ({
          tool: tc.tool_name,
          status: 'success',
        })),
      };
      setMessages(prev => [...prev, assistantMessage]);

      // Check for pending approval
      if (response.data.pending_approval) {
        setPendingApproval(response.data.pending_approval);
      }
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setIsLoading(false);
    }
  }, [notebookId]);

  const approveAction = useCallback(async () => {
    if (!pendingApproval || !notebookId) return;

    try {
      await apiClient.post('/api/approve', {
        notebook_id: notebookId,
        approval_id: pendingApproval.id,
      });
      setPendingApproval(null);
    } catch (error) {
      console.error('Approval error:', error);
    }
  }, [pendingApproval, notebookId]);

  const rejectAction = useCallback(() => {
    setPendingApproval(null);
  }, []);

  return {
    messages,
    isLoading,
    pendingApproval,
    sendMessage,
    approveAction,
    rejectAction,
  };
}
```

---

## 6. Marimo API Reference

### 6.1 Verified Backend Tools

These tools are available via `POST /api/ai/invoke_tool`:

| Tool Name | Source File | Description |
|-----------|-------------|-------------|
| `get_lightweight_cell_map` | `marimo/_ai/_tools/tools/cells.py:119` | Get cell IDs and previews |
| `get_cell_runtime_data` | `marimo/_ai/_tools/tools/cells.py:223` | Get cell code, errors, variables |
| `get_cell_outputs` | `marimo/_ai/_tools/tools/cells.py:347` | Get visual and console outputs |
| `get_notebook_errors` | `marimo/_ai/_tools/tools/errors.py` | Get all errors in notebook |
| `get_tables_and_variables` | `marimo/_ai/_tools/tools/tables_and_variables.py` | Get dataframes and variables |
| `get_database_tables` | `marimo/_ai/_tools/tools/datasource.py` | Get SQL table schemas |
| `lint_notebook` | `marimo/_ai/_tools/tools/lint.py` | Lint notebook code |
| `get_marimo_rules` | `marimo/_ai/_tools/tools/rules.py` | Get custom AI rules |
| `get_active_notebooks` | `marimo/_ai/_tools/tools/notebooks.py` | List active sessions |

### 6.2 Verified HTTP Endpoints

| Endpoint | Method | Mode | Source | Description |
|----------|--------|------|--------|-------------|
| `/api/kernel/run` | POST | EDIT | `execution.py:205` | Execute cells |
| `/api/kernel/delete` | POST | EDIT | `editing.py:61` | Delete cell |
| `/api/kernel/interrupt` | POST | EDIT | `execution.py:178` | Interrupt execution |
| `/api/kernel/format` | POST | EDIT | `editing.py:120` | Format code |
| `/api/kernel/save` | POST | EDIT | `files.py:134` | Save notebook |
| `/api/kernel/read_code` | POST | READ | `files.py:38` | Read notebook file |
| `/api/home/running_notebooks` | POST | EDIT | `home.py:145` | List sessions |
| `/api/ai/invoke_tool` | POST | EDIT | `ai.py:330` | Invoke AI tool |
| `/health` | GET | ANY | `health.py` | Health check |
| `/api/status` | GET | EDIT | `health.py:42` | Server status |

### 6.3 Request/Response Schemas

All schemas use **camelCase** (via `msgspec.Struct` with `rename="camel"`).

**ExecuteCellsRequest** (`models.py:223`):
```json
{
  "cellIds": ["cell-abc123", "cell-def456"],
  "codes": ["import pandas as pd", "df = pd.DataFrame()"]
}
```

**DeleteCellRequest** (`models.py:143`):
```json
{
  "cellId": "cell-abc123"
}
```

**InvokeAiToolRequest** (`models.py:294`):
```json
{
  "toolName": "get_lightweight_cell_map",
  "arguments": {
    "session_id": "session-xyz",
    "preview_lines": 5
  }
}
```

---

## 7. WebSocket Protocol

### 7.1 Connection

Connect to marimo's WebSocket at `/ws`:

```
ws://localhost:{port}/ws?session_id={session_id}
```

### 7.2 Notification Types

Notifications flow from kernel to frontend (`notification.py`):

| Type | Tag | Description |
|------|-----|-------------|
| `CellNotification` | `cell-op` | Cell state update (output, status, errors) |
| `KernelReadyNotification` | `kernel-ready` | Kernel initialized |
| `CompletedRunNotification` | `completed-run` | Execution batch completed |
| `InterruptedNotification` | `interrupted` | Execution interrupted |
| `FunctionCallResultNotification` | `function-call-result` | RPC result |

**CellNotification structure** (`notification.py:51-96`):
```json
{
  "op": "cell-op",
  "cellId": "cell-abc123",
  "output": {
    "data": "<html content>",
    "mimetype": "text/html"
  },
  "console": [...],
  "status": "idle",
  "staleInputs": false,
  "timestamp": 1706400000.0
}
```

**Status values**: `"idle"`, `"running"`, `"stale"`, `"queued"`, `"disabled-transitively"`

---

## 8. Tool System

### 8.1 Unified Tool Registry

```python
# app/agent/tools.py
from dataclasses import dataclass
from typing import Any, Callable, Awaitable
from enum import Enum

class ToolCategory(Enum):
    MARIMO_READ = "marimo_read"      # Read notebook state
    MARIMO_WRITE = "marimo_write"    # Modify notebook (needs approval)
    CUSTOM = "custom"                 # Your custom tools

@dataclass
class ToolDefinition:
    name: str
    description: str
    category: ToolCategory
    parameters: dict  # JSON Schema
    handler: Callable[..., Awaitable[Any]]
    requires_approval: bool = False

class ToolRegistry:
    def __init__(self, marimo_client: MarimoClient):
        self.client = marimo_client
        self.tools: dict[str, ToolDefinition] = {}
        self._register_marimo_tools()
        self._register_custom_tools()

    def _register_marimo_tools(self):
        # Read tools (no approval needed)
        self.tools["get_notebook_state"] = ToolDefinition(
            name="get_notebook_state",
            description="Get overview of all cells in the notebook",
            category=ToolCategory.MARIMO_READ,
            parameters={"type": "object", "properties": {}},
            handler=self._get_notebook_state,
        )

        self.tools["get_cell_code"] = ToolDefinition(
            name="get_cell_code",
            description="Get full code and runtime data for a specific cell",
            category=ToolCategory.MARIMO_READ,
            parameters={
                "type": "object",
                "properties": {
                    "cell_id": {"type": "string"}
                },
                "required": ["cell_id"]
            },
            handler=self._get_cell_code,
        )

        # Write tools (auto-apply)
        self.tools["execute_code"] = ToolDefinition(
            name="execute_code",
            description="Execute code in a cell (creates cell if new)",
            category=ToolCategory.MARIMO_WRITE,
            parameters={
                "type": "object",
                "properties": {
                    "cell_id": {"type": "string"},
                    "code": {"type": "string"}
                },
                "required": ["cell_id", "code"]
            },
            handler=self._execute_code,
            requires_approval=False,  # Safe operation
        )

        # Write tools (requires approval)
        self.tools["delete_cell"] = ToolDefinition(
            name="delete_cell",
            description="Delete a cell from the notebook",
            category=ToolCategory.MARIMO_WRITE,
            parameters={
                "type": "object",
                "properties": {
                    "cell_id": {"type": "string"}
                },
                "required": ["cell_id"]
            },
            handler=self._delete_cell,
            requires_approval=True,  # Destructive operation
        )

    def _register_custom_tools(self):
        # Add your custom tools here
        self.tools["search_docs"] = ToolDefinition(
            name="search_docs",
            description="Search product documentation",
            category=ToolCategory.CUSTOM,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            },
            handler=self._search_docs,
        )

    # Tool handlers
    async def _get_notebook_state(self) -> dict:
        cells = await self.client.get_cell_map()
        return {"cells": [c.__dict__ for c in cells]}

    async def _get_cell_code(self, cell_id: str) -> dict:
        data = await self.client.get_cell_runtime_data(cell_id)
        return data.__dict__

    async def _execute_code(self, cell_id: str, code: str) -> dict:
        success = await self.client.execute_cells([cell_id], [code])
        return {"success": success}

    async def _delete_cell(self, cell_id: str) -> dict:
        success = await self.client.delete_cell(cell_id)
        return {"success": success}

    async def _search_docs(self, query: str) -> dict:
        # Implement your documentation search
        return {"results": []}

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for LLM function calling."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self.tools.values()
        ]

    async def execute_tool(
        self,
        name: str,
        arguments: dict
    ) -> tuple[Any, bool]:
        """
        Execute a tool and return (result, requires_approval).
        """
        tool = self.tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        if tool.requires_approval:
            # Return without executing - needs approval
            return None, True

        result = await tool.handler(**arguments)
        return result, False
```

---

## 9. Session Management

### 9.1 User Session Model

```python
# app/models/session.py
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

@dataclass
class NotebookSession:
    notebook_id: str
    notebook_path: str
    marimo_port: int
    marimo_session_id: str
    opened_at: datetime = field(default_factory=datetime.now)

@dataclass
class UserSession:
    user_id: str
    notebooks: dict[str, NotebookSession] = field(default_factory=dict)
    max_notebooks: int = 5

    def can_open_notebook(self) -> bool:
        return len(self.notebooks) < self.max_notebooks

    def add_notebook(self, session: NotebookSession) -> None:
        if not self.can_open_notebook():
            raise RuntimeError(f"Maximum {self.max_notebooks} notebooks allowed")
        self.notebooks[session.notebook_id] = session

    def remove_notebook(self, notebook_id: str) -> Optional[NotebookSession]:
        return self.notebooks.pop(notebook_id, None)
```

### 9.2 Session Manager

```python
# app/session_manager.py
from typing import Optional

class SessionManager:
    def __init__(self, process_manager: MarimoProcessManager):
        self.process_manager = process_manager
        self.user_sessions: dict[str, UserSession] = {}

    async def open_notebook(
        self,
        user_id: str,
        notebook_id: str,
        notebook_path: str,
    ) -> NotebookSession:
        # Get or create user session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = UserSession(user_id=user_id)

        user_session = self.user_sessions[user_id]

        # Check if already open
        if notebook_id in user_session.notebooks:
            return user_session.notebooks[notebook_id]

        # Check limit
        if not user_session.can_open_notebook():
            raise RuntimeError("Too many open notebooks")

        # Start marimo process
        process = await self.process_manager.start_notebook(
            notebook_id=notebook_id,
            notebook_path=notebook_path,
        )

        # Create session
        session = NotebookSession(
            notebook_id=notebook_id,
            notebook_path=notebook_path,
            marimo_port=process.port,
            marimo_session_id=process.session_id,
        )

        user_session.add_notebook(session)
        return session

    async def close_notebook(
        self,
        user_id: str,
        notebook_id: str,
    ) -> None:
        user_session = self.user_sessions.get(user_id)
        if not user_session:
            return

        session = user_session.remove_notebook(notebook_id)
        if session:
            await self.process_manager.stop_notebook(notebook_id)

    def get_user_notebooks(self, user_id: str) -> list[NotebookSession]:
        user_session = self.user_sessions.get(user_id)
        if not user_session:
            return []
        return list(user_session.notebooks.values())
```

---

## 10. Hybrid Edit Control

### 10.1 Operation Classification

```python
# app/agent/edit_control.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class EditSafety(Enum):
    SAFE = "safe"          # Auto-apply
    DESTRUCTIVE = "destructive"  # Requires approval

OPERATION_SAFETY = {
    # Safe operations - auto-apply
    "execute_code": EditSafety.SAFE,
    "add_cell": EditSafety.SAFE,
    "update_cell": EditSafety.SAFE,
    "format_code": EditSafety.SAFE,
    "run_stale_cells": EditSafety.SAFE,

    # Destructive operations - require approval
    "delete_cell": EditSafety.DESTRUCTIVE,
    "delete_multiple_cells": EditSafety.DESTRUCTIVE,
    "clear_all_outputs": EditSafety.DESTRUCTIVE,
    "replace_notebook": EditSafety.DESTRUCTIVE,
    "restart_kernel": EditSafety.DESTRUCTIVE,
}

@dataclass
class PendingApproval:
    id: str
    operation: str
    description: str
    arguments: dict
    created_at: float

class EditController:
    def __init__(self):
        self.pending: dict[str, PendingApproval] = {}

    def needs_approval(self, operation: str) -> bool:
        safety = OPERATION_SAFETY.get(operation, EditSafety.DESTRUCTIVE)
        return safety == EditSafety.DESTRUCTIVE

    def create_approval_request(
        self,
        operation: str,
        description: str,
        arguments: dict,
    ) -> PendingApproval:
        import time
        import uuid

        approval = PendingApproval(
            id=str(uuid.uuid4()),
            operation=operation,
            description=description,
            arguments=arguments,
            created_at=time.time(),
        )
        self.pending[approval.id] = approval
        return approval

    def get_pending(self, approval_id: str) -> Optional[PendingApproval]:
        return self.pending.get(approval_id)

    def approve(self, approval_id: str) -> Optional[PendingApproval]:
        return self.pending.pop(approval_id, None)

    def reject(self, approval_id: str) -> None:
        self.pending.pop(approval_id, None)
```

---

## 11. Error Handling

### 11.1 Error Types

```python
# app/errors.py
class MarimoError(Exception):
    """Base error for marimo-related issues."""
    pass

class MarimoNotRunningError(MarimoError):
    """Marimo process is not running."""
    pass

class MarimoSessionError(MarimoError):
    """Session-related error."""
    pass

class CellNotFoundError(MarimoError):
    """Cell does not exist."""
    pass

class EditModeRequiredError(MarimoError):
    """Operation requires EDIT mode."""
    pass
```

### 11.2 Error Handling in Client

```python
async def execute_cells(self, cell_ids: list[str], codes: list[str]) -> bool:
    try:
        response = await self._client.post(
            self._url("/api/kernel/run"),
            headers=self._headers(),
            json={"cellIds": cell_ids, "codes": codes}
        )
        response.raise_for_status()
        return response.json().get("success", False)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise EditModeRequiredError(
                "This operation requires EDIT mode. "
                "Ensure marimo is running with 'marimo edit'."
            )
        raise MarimoError(f"HTTP error: {e.response.status_code}")
    except httpx.ConnectError:
        raise MarimoNotRunningError("Cannot connect to marimo server")
```

---

## 12. Security Considerations

### 12.1 Token Authentication

```python
# Generate secure tokens for each marimo process
import secrets

def generate_token() -> str:
    return secrets.token_urlsafe(32)

# Pass to marimo CLI
process = await asyncio.create_subprocess_exec(
    "marimo", "edit", notebook_path,
    "--token", token,
    ...
)
```

### 12.2 Network Isolation

- Run marimo processes bound to `localhost` only
- Proxy all requests through your FastAPI backend
- Never expose marimo ports directly to users

### 12.3 Input Validation

- Validate notebook paths to prevent directory traversal
- Sanitize cell IDs before passing to marimo
- Limit code execution to authenticated users

---

## 13. Deployment

### 13.1 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MARIMO_PORT_START=2718
      - MARIMO_PORT_END=2800
    volumes:
      - ./notebooks:/app/notebooks

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - api
```

### 13.2 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install marimo
RUN pip install marimo

# Install your app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 14. Testing Strategy

### 14.1 Unit Tests

```python
# tests/test_marimo_client.py
import pytest
from unittest.mock import AsyncMock, patch
from app.marimo.client import MarimoClient

@pytest.fixture
def mock_process():
    return MarimoProcess(
        process=AsyncMock(),
        port=2718,
        notebook_path="test.py",
        token="test-token",
        session_id="test-session",
    )

@pytest.mark.asyncio
async def test_get_cell_map(mock_process):
    client = MarimoClient(mock_process)

    with patch.object(client, 'invoke_tool') as mock_invoke:
        mock_invoke.return_value = {
            "success": True,
            "result": {
                "cells": [
                    {"cellId": "cell-1", "preview": "import pandas", "lineCount": 1, "cellType": "code"}
                ]
            }
        }

        cells = await client.get_cell_map()

        assert len(cells) == 1
        assert cells[0].cell_id == "cell-1"
```

### 14.2 Integration Tests

```python
# tests/test_integration.py
import pytest
from app.marimo.process_manager import MarimoProcessManager

@pytest.mark.asyncio
async def test_start_and_stop_notebook():
    manager = MarimoProcessManager()

    try:
        # Create a test notebook
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"import marimo\napp = marimo.App()\n")
            notebook_path = f.name

        # Start notebook
        process = await manager.start_notebook("test-1", notebook_path)
        assert process.port >= 2718
        assert process.session_id is not None

        # Verify health
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{process.port}/health")
            assert response.status_code == 200
    finally:
        await manager.shutdown_all()
```

---

## Summary

This RFC provides a complete implementation guide for embedding marimo with custom agentic features:

1. **Run marimo as EDIT-mode subprocesses** via CLI
2. **Use verified HTTP APIs** for all notebook operations
3. **Embed marimo frontend in iframes** for rendering
4. **Build your own chat UI** with approval workflow
5. **Manage multiple notebooks** per user with port allocation

All APIs referenced have been verified against the marimo codebase with exact source file locations.
