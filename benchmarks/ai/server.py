from __future__ import annotations

import json
import os
import site
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import venv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self, cast

from benchmarks.ai.models import (
    HarnessVariant,
    JSONValue,
    TokenUsage,
    ToolCallMetrics,
)
from benchmarks.ai.vercel_stream import (
    AssistantMessageBuilder,
    StructuredCompletionBuilder,
    parse_sse,
    serialized_chars,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


TRACE_ID_HEADER = "X-Marimo-Trace-Id"
EVAL_RUN_HEADER = "Marimo-AI-Eval-Run-Id"
EVAL_SCENARIO_HEADER = "Marimo-AI-Eval-Scenario-Id"
EVAL_TURN_HEADER = "Marimo-AI-Eval-Turn"
EVAL_TRIAL_HEADER = "Marimo-AI-Eval-Trial-Id"
EVAL_VARIANT_HEADER = "Marimo-AI-Eval-Variant-Id"
EVAL_REPETITION_HEADER = "Marimo-AI-Eval-Repetition"
TOOL_STRATEGY_HEADER = "Marimo-AI-Tool-Strategy"
INCLUDE_USAGE_HEADER = "Marimo-AI-Include-Usage"
_SUMMARY_MARKER = "__MARIMO_AI_EVAL__"


def parse_summary_response(body: str) -> dict[str, JSONValue]:
    """Read a summary whose stdout may be split across SSE messages."""
    fragments: list[str] = []
    errors: list[str] = []
    for block in body.split("\n\n"):
        event = ""
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        if not data_lines:
            continue
        value = json.loads("\n".join(data_lines))
        if not isinstance(value, dict):
            continue
        chunk_type = str(value.get("type", ""))
        data = value.get("data", "")
        if isinstance(data, dict):
            data = data.get("data", "")
        if event == "stdout" or chunk_type == "stdout":
            fragments.append(str(data))
        elif event == "stderr" or chunk_type == "stderr":
            errors.append(str(data))

    output = "".join(fragments)
    if _SUMMARY_MARKER not in output:
        detail = errors[-1].strip() if errors else "no stdout was returned"
        raise RuntimeError(
            "analysis_summary was not found in the live kernel: " + detail
        )
    payload = output.split(_SUMMARY_MARKER, 1)[1].lstrip()
    if not payload:
        raise RuntimeError("analysis_summary output was empty")
    value, _ = json.JSONDecoder().raw_decode(payload)
    if not isinstance(value, dict):
        raise TypeError("analysis_summary must be a dictionary")
    return cast(dict[str, JSONValue], value)


@dataclass(frozen=True)
class ChatTurn:
    message: dict[str, Any]
    text: str
    tool_calls: int
    tool_errors: int
    usage: TokenUsage
    trace_id: str
    tool_metrics: tuple[ToolCallMetrics, ...]
    effective_history_chars: int


@dataclass(frozen=True)
class HttpResponse:
    body: str
    trace_id: str


class HttpRequestError(RuntimeError):
    def __init__(self, status_code: int, body: str, trace_id: str) -> None:
        super().__init__(f"HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body
        self.trace_id = trace_id


@dataclass(frozen=True)
class GenerateTurn:
    cells: tuple[dict[str, str], ...]
    usage: TokenUsage
    trace_id: str


@dataclass(frozen=True)
class InlineTurn:
    completion: str
    trace_id: str


@dataclass
class MarimoServer:
    root: Path
    notebook: Path
    model: str
    timeout_seconds: float
    eval_run_id: str
    scenario_id: str
    trial_id: str
    repetition: int
    variant: HarnessVariant
    isolated_environment: bool = False
    process: subprocess.Popen[bytes] | None = None
    base_url: str = ""
    session_id: str = field(
        default_factory=lambda: f"eval_{uuid.uuid4().hex[:12]}"
    )
    _stderr_file: Any = None
    _websocket: Any = None
    _drain_thread: threading.Thread | None = None
    _stop_drain: threading.Event = field(default_factory=threading.Event)
    _cell_ids_by_name: dict[str, str] = field(default_factory=dict)
    _cell_codes_by_name: dict[str, str] = field(default_factory=dict)

    def __enter__(self) -> Self:
        self._write_config()
        python, environment = self._server_environment()
        port = _free_port()
        self.base_url = f"http://127.0.0.1:{port}"
        stderr_path = self.root / "marimo-server.log"
        self._stderr_file = stderr_path.open("wb")
        self.process = subprocess.Popen(
            [
                str(python),
                "-m",
                "marimo",
                "edit",
                str(self.notebook),
                "--headless",
                "--no-token",
                "--no-skew-protection",
                "--port",
                str(port),
            ],
            cwd=self.root,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=self._stderr_file,
        )
        self._wait_until_ready(stderr_path)
        self._connect_session()
        return self

    def _server_environment(self) -> tuple[Path, dict[str, str]]:
        environment = os.environ.copy()
        if not self.isolated_environment:
            return Path(sys.executable), environment

        environment_root = self.root / ".benchmark-venv"
        venv.EnvBuilder(
            with_pip=False,
            symlinks=os.name != "nt",
        ).create(environment_root)
        if os.name == "nt":
            python = environment_root / "Scripts" / "python.exe"
        else:
            python = environment_root / "bin" / "python"

        process = subprocess.run(
            [
                str(python),
                "-c",
                "import site; print(site.getsitepackages()[0])",
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        site_packages = Path(process.stdout.strip())
        parent_paths = [
            Path(path).resolve()
            for path in site.getsitepackages()
            if Path(path).exists()
        ]
        repository_root = Path(__file__).resolve().parents[2]
        (site_packages / "marimo-benchmark-parent.pth").write_text(
            "\n".join(str(path) for path in [repository_root, *parent_paths])
            + "\n",
            encoding="utf-8",
        )

        environment["VIRTUAL_ENV"] = str(environment_root)
        environment.pop("UV_PROJECT_ENVIRONMENT", None)
        environment["PATH"] = os.pathsep.join(
            [str(python.parent), environment.get("PATH", "")]
        )
        return python, environment

    def __exit__(self, *_: object) -> None:
        self._stop_drain.set()
        if self._websocket is not None:
            try:
                self._websocket.close()
            except Exception:
                pass
        if self._drain_thread is not None:
            self._drain_thread.join(timeout=2)
        if self.process is not None and self.process.poll() is None:
            try:
                self._post("/api/shutdown", {})
            except Exception:
                # Fall back to terminating the process if graceful shutdown is
                # unavailable. The benchmark artifacts still retain the log.
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        if self._stderr_file is not None:
            self._stderr_file.close()

    def _write_config(self) -> None:
        # Keep benchmark results independent of a developer's configured MCP
        # servers and other editor preferences. Environment variables are
        # still inherited by the subprocess for W&B and OpenTelemetry.
        (self.root / ".marimo.toml").touch()
        model = (
            self.model
            if self.model.startswith("wandb/")
            else f"wandb/{self.model}"
        )
        rules = (
            f"rules = {json.dumps(self.variant.custom_rules)}\n"
            if self.variant.custom_rules
            else ""
        )
        max_tokens = (
            f"max_tokens = {self.variant.max_tokens}\n"
            if self.variant.max_tokens is not None
            else ""
        )
        config = f'''[tool.marimo.ai]
mode = "{self.variant.mode}"
{max_tokens}
{rules}

[tool.marimo.ai.models]
chat_model = "{model}"
edit_model = "{model}"
autocomplete_model = "{model}"

[tool.marimo.ai.wandb]
api_key = "env:WANDB_API_KEY"
base_url = "https://api.inference.wandb.ai/v1/"
'''
        (self.root / "pyproject.toml").write_text(config, encoding="utf-8")

    def _wait_until_ready(self, stderr_path: Path) -> None:
        assert self.process is not None
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                tail = stderr_path.read_text(
                    encoding="utf-8", errors="replace"
                )[-4000:]
                raise RuntimeError(
                    f"marimo server exited with {self.process.returncode}:\n{tail}"
                )
            try:
                with urllib.request.urlopen(self.base_url, timeout=1):
                    return
            except urllib.error.HTTPError:
                # A source checkout may not have built frontend assets, so the
                # root route can return 404 even though the API is ready.
                return
            except (OSError, urllib.error.URLError):
                time.sleep(0.05)
        tail = stderr_path.read_text(encoding="utf-8", errors="replace")[
            -4000:
        ]
        raise TimeoutError(f"marimo server did not start:\n{tail}")

    def _connect_session(self) -> None:
        import websockets.sync.client

        self._websocket = websockets.sync.client.connect(
            f"{self.base_url.replace('http', 'ws')}/ws?session_id={self.session_id}",
            open_timeout=10,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            message = json.loads(self._websocket.recv(timeout=5))
            if message.get("op") == "kernel-ready":
                data = message.get("data", {})
                self._cell_ids_by_name = {
                    str(name): str(cell_id)
                    for name, cell_id in zip(
                        data.get("names", ()),
                        data.get("cell_ids", ()),
                        strict=True,
                    )
                    if name != "_"
                }
                self._cell_codes_by_name = {
                    str(name): str(code)
                    for name, code in zip(
                        data.get("names", ()),
                        data.get("codes", ()),
                        strict=True,
                    )
                    if name != "_"
                }
                break
        else:
            raise TimeoutError("kernel-ready was not received")

        def drain() -> None:
            while not self._stop_drain.is_set():
                try:
                    self._websocket.recv(timeout=0.25)
                except TimeoutError:
                    continue
                except Exception:
                    return

        self._drain_thread = threading.Thread(target=drain, daemon=True)
        self._drain_thread.start()

    def edit_cell(self, cell_name: str, code: str) -> None:
        """Apply an out-of-band edit through the editor's live run API."""
        try:
            cell_id = self._cell_ids_by_name[cell_name]
        except KeyError as exc:
            available = ", ".join(sorted(self._cell_ids_by_name))
            raise ValueError(
                f"Unknown named cell {cell_name!r}; available: {available}"
            ) from exc

        self._post(
            "/api/kernel/run",
            {"cellIds": [cell_id], "codes": [code]},
        )
        self._cell_codes_by_name[cell_name] = code

        # The run endpoint queues work. Give the kernel a chance to observe
        # the command, then wait on the same status endpoint used by clients.
        time.sleep(0.1)
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            if self._kernel_status() == "idle":
                return
            time.sleep(0.05)
        raise TimeoutError(f"Live edit of cell {cell_name!r} did not finish")

    def _kernel_status(self) -> str:
        request = urllib.request.Request(
            f"{self.base_url}/api/kernel/status",
            headers={"Marimo-Session-Id": self.session_id},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        return str(payload["state"])

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        turn_number: int,
    ) -> ChatTurn:
        effective_messages = messages
        if self.variant.tool_strategy == "hybrid_balanced":
            from marimo._server.ai.tools.code_mode import (
                compact_hybrid_history,
            )

            effective_messages = compact_hybrid_history(messages)
        body = {
            "id": self.session_id,
            "includeOtherCode": "",
            "uiMessages": messages,
            "options": {"webSearch": False},
        }
        response = self._post(
            "/api/ai/chat",
            body,
            headers={
                "Accept": "text/event-stream",
                EVAL_RUN_HEADER: self.eval_run_id,
                EVAL_SCENARIO_HEADER: self.scenario_id,
                EVAL_TURN_HEADER: str(turn_number),
                EVAL_TRIAL_HEADER: self.trial_id,
                EVAL_VARIANT_HEADER: self.variant.id,
                EVAL_REPETITION_HEADER: str(self.repetition),
                TOOL_STRATEGY_HEADER: self.variant.tool_strategy,
                INCLUDE_USAGE_HEADER: "true",
            },
        )
        builder = AssistantMessageBuilder()
        for chunk in parse_sse(response.body):
            builder.add(chunk)
        return ChatTurn(
            message=builder.build(),
            text=builder.text(),
            tool_calls=builder.tool_calls,
            tool_errors=builder.tool_errors,
            usage=builder.usage,
            trace_id=response.trace_id,
            tool_metrics=builder.tool_metrics,
            effective_history_chars=serialized_chars(effective_messages),
        )

    def generate(
        self,
        prompt: str,
        *,
        include_other_code: str,
        context_plain_text: str,
    ) -> GenerateTurn:
        response = self._post(
            "/api/ai/completion",
            {
                "id": self.session_id,
                "prompt": "",
                "code": "",
                "includeOtherCode": include_other_code,
                "context": {
                    "plainText": context_plain_text,
                    "schema": [],
                    "variables": [],
                },
                "language": "python",
                "uiMessages": [
                    {
                        "id": f"user-{uuid.uuid4().hex[:12]}",
                        "role": "user",
                        "parts": [{"type": "text", "text": prompt}],
                    }
                ],
            },
            headers=self._eval_headers(turn=1, variant_id="generate"),
        )
        builder = StructuredCompletionBuilder(
            data_type="data-notebook-cells-completion"
        )
        for chunk in parse_sse(response.body):
            builder.add(chunk)
        payload = builder.result()
        raw_cells = payload.get("cells")
        if not isinstance(raw_cells, list):
            raise TypeError("Generate with AI returned an invalid cells value")
        cells: list[dict[str, str]] = []
        for raw_cell in raw_cells:
            if not isinstance(raw_cell, dict):
                raise TypeError("Generate with AI returned an invalid cell")
            language = raw_cell.get("language")
            code = raw_cell.get("code")
            if not isinstance(language, str) or not isinstance(code, str):
                raise TypeError("Generate with AI returned an invalid cell")
            cells.append({"language": language, "code": code})
        return GenerateTurn(
            cells=tuple(cells),
            usage=builder.usage,
            trace_id=response.trace_id,
        )

    def inline(
        self,
        *,
        prefix: str,
        suffix: str,
        language: str,
    ) -> InlineTurn:
        response = self._post(
            "/api/ai/inline_completion",
            {"prefix": prefix, "suffix": suffix, "language": language},
            headers=self._eval_headers(turn=1, variant_id="inline"),
        )
        return InlineTurn(
            completion=response.body,
            trace_id=response.trace_id,
        )

    def _eval_headers(self, *, turn: int, variant_id: str) -> dict[str, str]:
        return {
            EVAL_RUN_HEADER: self.eval_run_id,
            EVAL_SCENARIO_HEADER: self.scenario_id,
            EVAL_TURN_HEADER: str(turn),
            EVAL_TRIAL_HEADER: self.trial_id,
            EVAL_VARIANT_HEADER: variant_id,
            EVAL_REPETITION_HEADER: str(self.repetition),
            INCLUDE_USAGE_HEADER: "true",
        }

    def inspect_summary(self) -> dict[str, JSONValue]:
        code = (
            "import json\n"
            "print('__MARIMO_AI_EVAL__' + json.dumps(analysis_summary, "
            "sort_keys=True, default=str))"
        )
        response = self._post("/api/kernel/execute", {"code": code})
        return parse_summary_response(response.body)

    def _post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        request_headers = {
            "Content-Type": "application/json",
            "Marimo-Session-Id": self.session_id,
            **(headers or {}),
        }
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            method="POST",
            data=json.dumps(body).encode(),
            headers=request_headers,
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                return HttpResponse(
                    body=response.read().decode(),
                    trace_id=response.headers.get(TRACE_ID_HEADER, ""),
                )
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode(errors="replace")
            trace_id = exc.headers.get(TRACE_ID_HEADER, "")
            raise HttpRequestError(exc.code, response_body, trace_id) from exc
