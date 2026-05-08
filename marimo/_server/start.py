# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
import threading
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

import uvicorn

from marimo._cli.print import echo
from marimo._cli.sandbox import SandboxMode
from marimo._config.config import PartialMarimoConfig
from marimo._config.manager import get_default_config_manager
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._mcp.setup import McpType, setup_mcp_server
from marimo._messaging.notification import StartupLogsNotification
from marimo._runtime.commands import SerializedCLIArgs
from marimo._runtime.parent_poller import start_parent_poller
from marimo._server.api import lifespans
from marimo._server.config import (
    StarletteServerStateInit,
)
from marimo._server.lsp import CompositeLspServer, NoopLspServer
from marimo._server.main import create_starlette_app
from marimo._server.registry import LIFESPAN_REGISTRY
from marimo._server.session_manager import SessionManager
from marimo._server.tokens import AuthToken
from marimo._server.utils import (
    initialize_asyncio,
    initialize_fd_limit,
)
from marimo._server.uvicorn_utils import initialize_signals
from marimo._server.workspace import (
    DirectoryWorkspace,
    NotebookWorkspace,
)
from marimo._session.model import SessionMode
from marimo._tracer import LOGGER
from marimo._utils.lifespans import Lifespans
from marimo._utils.net import find_free_port

if TYPE_CHECKING:
    from marimo._cli.tips import CliTip

DEFAULT_PORT = 2718


def _execute_startup_command(
    command: str, session_manager: SessionManager
) -> None:
    """Execute a server startup command in a background thread and stream logs."""

    def run_command() -> None:
        buffer = StartupLogsNotification(content="", status="start")

        def write_to_all_sessions(
            content: StartupLogsNotification,
            buffer: StartupLogsNotification,
        ) -> None:
            for session in session_manager.sessions.values():
                # Clear buffer if it has content
                if buffer.content != "":
                    session.notify(buffer, from_consumer_id=None)
                    buffer = StartupLogsNotification(
                        content="", status="start"
                    )
                session.notify(content, from_consumer_id=None)
            buffer.content += content.content
            buffer.status = content.status

        try:
            # Broadcast start message to all sessions
            write_to_all_sessions(
                StartupLogsNotification(content="", status="start"), buffer
            )

            # Execute the command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Stream stderr to stdout
                text=True,
                universal_newlines=True,
            )

            # Stream output line by line
            if process.stdout:
                for line in process.stdout:
                    write_to_all_sessions(
                        StartupLogsNotification(content=line, status="append"),
                        buffer,
                    )
                    echo(line, nl=False)

            # Wait for process to complete
            return_code = process.wait()

            # Broadcast completion message
            final_message = (
                f"\nProcess completed with exit code: {return_code}\n"
            )
            write_to_all_sessions(
                StartupLogsNotification(content=final_message, status="done"),
                buffer,
            )
            echo(final_message)

        except Exception as e:
            # Broadcast error message
            error_message = f"\nError executing startup command: {e!s}\n"
            write_to_all_sessions(
                StartupLogsNotification(content=error_message, status="done"),
                buffer,
            )
            echo(error_message)

    # Run the command in a background thread
    thread = threading.Thread(target=run_command)
    thread.start()


def _resolve_proxy(port: int, host: str, proxy: str | None) -> tuple[int, str]:
    """Provided that there is a proxy, utilize the host and port of the proxy.

    -----------------         Communication has to be consistent
    |   User        | ----    so Starlette only needs to know the
    -----------------     |   external facing endpoint, while uvi-
                          |   corn handles the actual running of
                          v   the app.
                  -----------------
      e.g. nginx  |   Proxy       |
                  -----------------
                          |
                          v
                  -----------------
        the app   |   marimo      |
       (uvicorn)  -----------------


    If the proxy is provided, it will default to port 80 (443 for https://).
    Supports bare hostnames, host:port, and full URLs with a scheme.
    e.g. `example.com:8080`, `https://example.com`, `https://example.com:8443`
    """
    if not proxy:
        return port, host

    # Prefix with "//" so urlparse treats the value as a netloc rather than a
    # path when no scheme is present — handles "host", "host:port", and full
    # "scheme://host:port" forms uniformly.
    parse_target = proxy if "://" in proxy else f"//{proxy}"

    try:
        parsed = urlparse(parse_target)

        # parsed.hostname strips brackets from IPv6 addresses
        # (e.g. [::1] → ::1)
        external_host = parsed.hostname
        parsed_port = parsed.port
    except ValueError:
        LOGGER.warning(
            "Ignoring invalid proxy value %r; falling back to host=%r, port=%r",
            proxy,
            host,
            port,
        )
        return port, host

    # Bare-port inputs like ":8080" leave parsed.hostname empty (urlparse
    # sees an empty netloc with an explicit port); fall back to the
    # original `host` arg rather than using the literal proxy string —
    # which otherwise becomes the nonsense public hostname ":8080".
    if not external_host:
        external_host = host

    if parsed_port is not None:
        external_port = parsed_port
    elif parsed.scheme == "https":
        external_port = 443
    else:
        external_port = 80

    return external_port, external_host


def start(
    *,
    workspace: NotebookWorkspace,
    mode: SessionMode,
    development_mode: bool,
    quiet: bool,
    include_code: bool,
    ttl_seconds: int | None,
    headless: bool,
    port: int | None,
    host: str,
    proxy: str | None,
    watch: bool,
    cli_args: SerializedCLIArgs,
    argv: list[str],
    base_url: str = "",
    allow_origins: tuple[str, ...] | None = None,
    auth_token: AuthToken | None,
    redirect_console_to_browser: bool,
    skew_protection: bool,
    remote_url: str | None = None,
    mcp: McpType | None = None,
    mcp_allow_remote: bool = False,
    server_startup_command: str | None = None,
    asset_url: str | None = None,
    timeout: float | None = None,
    sandbox_mode: SandboxMode | None = None,
    startup_tip: CliTip | None = None,
    show_tracebacks: bool | None = None,
) -> None:
    """
    Start the server.
    """
    import packaging.version

    # In single-file sandbox mode, uv becomes our direct parent. So we
    # watch the outer CLI's PID, terminating if the CLI terminates.
    ancestor_pid_env = os.environ.get("MARIMO_ANCESTOR_PID")
    if ancestor_pid_env:
        try:
            start_parent_poller(
                parent_pid=os.getppid(),
                ancestor_pid=int(ancestor_pid_env),
            )
        except ValueError:
            LOGGER.warning(
                "Ignoring invalid MARIMO_ANCESTOR_PID=%r", ancestor_pid_env
            )

    # Defaults when mcp is enabled
    if mcp:
        # Turn on watch mode
        watch = True
        # Turn off skew protection for MCP server
        # since it is more convenient to connect to.
        # Skew protection is not a security thing, but rather
        # prevents connecting to old servers.
        skew_protection = False

    # Find a free port if none is specified
    # if the user specifies a port, we don't try to find a free one
    port = port or find_free_port(DEFAULT_PORT, addr=host)

    # This is the path that will be used to read the project configuration
    start_path: str | None = None
    if (single_file := workspace.single_file()) is not None:
        start_path = single_file.path
    elif (directory := workspace.directory) is not None:
        start_path = directory
    else:
        start_path = os.getcwd()

    config_reader = get_default_config_manager(current_path=start_path)

    lsp_composite_server: CompositeLspServer | None = None
    if mode == SessionMode.EDIT:
        lsp_composite_server = CompositeLspServer(
            config_reader=config_reader,
            min_port=DEFAULT_PORT + 400,
        )

    if watch and config_reader.is_auto_save_enabled:
        LOGGER.warning("Enabling watch mode may interfere with auto-save.")

    if (
        mode == SessionMode.RUN
        and watch
        and isinstance(workspace, DirectoryWorkspace)
    ):
        LOGGER.warning(
            "Using `marimo run <folder> --watch`: gallery files are "
            "discovered dynamically. New notebooks created in this directory "
            "may appear in the gallery and execute code when opened. Use "
            "trusted directories and authentication controls."
        )

    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        config_reader = config_reader.with_overrides(
            {
                # Currently, only uv is supported for managing script metadata
                # If this changes, instead we should only update the config
                # if the user's package manager does not support sandboxes.
                "package_management": {
                    "manager": "uv",
                }
            }
        )

    is_multi = workspace.get_unique_file_key() is None
    isolate_apps = is_multi and config_reader.experimental.get(
        "isolate_apps", False
    )

    # Apply CLI overrides for runtime config if explicitly set
    if show_tracebacks is not None:
        config_reader = config_reader.with_overrides(
            cast(
                PartialMarimoConfig,
                {"runtime": {"show_tracebacks": show_tracebacks}},
            )
        )

    session_manager = SessionManager(
        workspace=workspace,
        mode=mode,
        quiet=quiet,
        include_code=include_code,
        ttl_seconds=ttl_seconds,
        lsp_server=lsp_composite_server or NoopLspServer(),
        config_manager=config_reader,
        cli_args=cli_args,
        argv=argv,
        auth_token=auth_token,
        redirect_console_to_browser=redirect_console_to_browser,
        watch=watch,
        sandbox_mode=sandbox_mode,
        isolate_apps=isolate_apps,
    )

    log_level = "info" if development_mode else "error"

    lifespans_list = [
        lifespans.lsp,
        lifespans.mcp,
        lifespans.etc,
        lifespans.signal_handler,
        lifespans.logging,
        lifespans.open_browser,
        lifespans.tool_manager,
        lifespans.server_registry,
        lifespans.reap_subprocesses,
        *LIFESPAN_REGISTRY.get_all(),
    ]

    mcp_enabled = mcp is not None and mode == SessionMode.EDIT

    (external_port, external_host) = _resolve_proxy(port, host, proxy)
    enable_auth = not AuthToken.is_empty(session_manager.auth_token)
    app = create_starlette_app(
        base_url=base_url,
        host=external_host,
        lifespan=Lifespans(lifespans_list),
        allow_origins=allow_origins,
        enable_auth=enable_auth,
        lsp_servers=list(lsp_composite_server.servers.values())
        if lsp_composite_server is not None
        else None,
        skew_protection=skew_protection,
        timeout=timeout,
    )

    if mcp_enabled and mcp is not None:
        # setup_mcp_server returns the lifespan for the chosen mode;
        # appending it to lifespans_list works because Lifespans stores
        # a reference to the list and iterates it at startup time.
        lifespans_list.append(
            setup_mcp_server(app, mcp, allow_remote=mcp_allow_remote)
        )

    init_state = StarletteServerStateInit(
        port=external_port,
        host=external_host,
        base_url=base_url,
        asset_url=asset_url,
        headless=headless,
        quiet=quiet,
        session_manager=session_manager,
        config_manager=config_reader,
        remote_url=remote_url,
        mcp_server_enabled=mcp_enabled,
        skew_protection=skew_protection,
        enable_auth=enable_auth,
        startup_tip=startup_tip,
    )
    init_state.apply(app.state)

    # Resource initialization
    # Increase the limit on open file descriptors to prevent resource
    # exhaustion when opening multiple notebooks in the same server.
    initialize_fd_limit(limit=4096)
    initialize_signals()

    # Platform-specific initialization of the event loop policy (Windows
    # requires SelectorEventLoop).
    initialize_asyncio()

    if packaging.version.Version(
        uvicorn.__version__
    ) >= packaging.version.Version("0.36.0"):
        # uvicorn 0.36.0 introduced custom event loop policies, and uses a loop
        # factory instead of asyncio's global event loop policy (the latter was
        # deprecated in Python 3.14).
        #
        # We have to use a SelectorEventLoop on Windows in particular (because
        # we use the add_reader API); Selector is already the default on Unix.
        #
        # The syntax is awkward: <module>:function
        edit_loop_policy = "asyncio:SelectorEventLoop"
    else:
        # Older versions of uvicorn use the globally configured event
        # loop policy
        edit_loop_policy = "asyncio"

    # Under uvloop, reading the socket we monitor under add_reader()
    # occasionally throws BlockingIOError (errno 11, or errno 35,
    # ...). RUN mode no longer uses a socket (it has no IPC) but EDIT
    # does, so force asyncio.
    loop_policy = edit_loop_policy if mode == SessionMode.EDIT else "auto"

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            port=port,
            host=host.strip(
                "[]"
            ),  # uvicorn expects bare IPv6 without brackets
            log_level=log_level,
            # uvicorn times out HTTP connections (i.e. TCP sockets) every 5
            # seconds by default; for some reason breaks the server in
            # mysterious ways (it stops processing requests) in edit mode.
            timeout_keep_alive=300 if mode == SessionMode.RUN else int(1e9),
            # ping the websocket once a second to prevent intermittent
            # disconnections
            ws_ping_interval=1,
            # close the websocket if we don't receive a pong after 60 seconds
            ws_ping_timeout=60,
            timeout_graceful_shutdown=1,
            # loop can take an arbitrary string but mypy is complaining
            # expecting it to be a Literal
            loop=loop_policy,  # type:ignore[arg-type]
        )
    )
    app.state.server = server

    # Execute server startup command if provided
    if server_startup_command:
        _execute_startup_command(server_startup_command, session_manager)

    server.run()
