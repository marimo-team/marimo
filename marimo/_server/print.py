# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys

from marimo._cli.print import bold, green, light_blue, muted, yellow
from marimo._cli.tips import CliTip
from marimo._config.config import MarimoConfig, MCPConfig
from marimo._utils.print import print_, print_tabbed

UTF8_SUPPORTED = False

try:
    "🌊🍃".encode(sys.stdout.encoding)
    UTF8_SUPPORTED = True
except Exception:
    pass


def print_startup(
    *,
    file_name: str | None,
    url: str,
    run: bool,
    new: bool,
    network: bool,
    startup_tip: CliTip | None = None,
) -> None:
    print_()
    if file_name is not None and not run:
        print_tabbed(
            f"{green(f'Edit {os.path.basename(file_name)} in your browser', bold=True)} {_utf8('📝')}"
        )
    elif file_name is not None and run:
        print_tabbed(
            f"{green(f'Running {os.path.basename(file_name)}', bold=True)} {_utf8('⚡')}"
        )
    elif new:
        print_tabbed(
            f"{green('Create a new notebook in your browser', bold=True)} {_utf8('📝')}"
        )
    else:
        print_tabbed(
            f"{green('Create or edit notebooks in your browser', bold=True)} {_utf8('📝')}"
        )
    print_()
    print_tabbed(f"{_utf8('➜')}  {green('URL')}: {_colorized_url(url)}")
    if network:
        try:
            print_tabbed(
                f"{_utf8('➜')}  {green('Network')}: {_colorized_url(_get_network_url(url))}"
            )
        except Exception:
            # If we can't get the network URL, just skip it
            pass
    if startup_tip is not None:
        print_()
        summary, action = _format_startup_tip(startup_tip)
        print_tabbed(summary)
        if action is not None:
            print_tabbed(action, n_tabs=2)
    print_()


def print_shutdown() -> None:
    print_()
    print_tabbed(
        "\033[32mThanks for using marimo!\033[0m {}".format(_utf8("🌊🍃"))
    )
    print_()


def _get_network_url(url: str) -> str:
    import socket

    hostname = socket.gethostname()
    try:
        # Find a non-loopback IPv4 address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't need to be reachable
        s.connect(("255.255.255.254", 1))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            # Get all IPs for the hostname
            all_ips = socket.getaddrinfo(hostname, None)
            # Filter for IPv4 addresses that aren't loopback
            for ip_info in all_ips:
                family, _, _, _, addr = ip_info
                if family == socket.AF_INET and not str(addr[0]).startswith(
                    "127."
                ):
                    local_ip = addr[0]
                    break
            else:
                # If no suitable IP found, fall back to hostname
                local_ip = hostname
        except Exception:
            # Final fallback to hostname
            local_ip = hostname

    # Replace the host part of the URL with the local IP
    from urllib.parse import urlparse, urlunparse

    parsed_url = urlparse(url)
    new_netloc = local_ip + (f":{parsed_url.port}" if parsed_url.port else "")
    new_url = urlunparse(parsed_url._replace(netloc=new_netloc))

    return new_url


def _colorized_url(url_string: str) -> str:
    from urllib.parse import urlparse

    url = urlparse(url_string)
    if url.query:
        query = muted(f"?{url.query}")
    else:
        query = ""

    hostname = url.hostname or ""
    # IPv6 addresses need brackets when embedded in a URL (RFC 3986)
    if ":" in hostname:
        hostname = f"[{hostname}]"
    url_string = f"{url.scheme}://{hostname}"
    # raw https and http urls do not have a port to parse
    try:
        if url.port:
            url_string += f":{url.port}"
    except Exception:
        # If the port is not a number, don't include it
        pass

    return bold(
        f"{url_string}{url.path}{query}",
    )


def _utf8(msg: str) -> str:
    return msg if UTF8_SUPPORTED else ""


def _format_startup_tip(tip: CliTip) -> tuple[str, str | None]:
    emoji = _utf8("💡")
    label = (
        f"{emoji} {yellow('Tip:', bold=True)}"
        if emoji
        else yellow("Tip:", bold=True)
    )
    summary = f"{label} {tip.text}"
    if tip.command is not None:
        return summary, f"{muted('$')} {light_blue(tip.command)}"
    if tip.link is not None:
        return summary, f"{muted('Guide:')} {light_blue(tip.link)}"
    return summary, None


def print_experimental_features(config: MarimoConfig) -> None:
    if "experimental" not in config:
        return

    keys = set(config["experimental"].keys())

    # These experiments have been released
    finished_experiments = {
        "rtc",
        "lsp",
        "chat_sidebar",
        "inline_ai_tooltip",
        "multi_column",
        "scratchpad",
        "tracing",
        "markdown",
        "sql_engines",
        "secrets",
        "reactive_tests",
        "toplevel_defs",
        "setup_cell",
        "mcp_docs",
        "sql_linter",
        "sql_mode",
        "performant_table_charts",
        "chat_modes",
        "server_side_pdf_export",
        "storage_inspector",
    }
    keys = keys - finished_experiments

    if len(keys) == 0:
        return

    print_tabbed(
        f"{_utf8('🧪')} {green('Experimental features (use with caution)')}: {', '.join(keys)}"
    )


def print_mcp_server(mcp_url: str, server_token: str | None) -> None:
    """Print MCP server configuration when MCP is enabled."""
    print_()
    print_tabbed(
        f"{_utf8('🔗')} {green('Experimental MCP server configuration', bold=True)}"
    )
    print_tabbed(
        f"{_utf8('➜')}  {green('MCP server URL')}: {_colorized_url(mcp_url)}"
    )
    # Add to Claude code
    print_tabbed(
        f"{_utf8('➜')}  {green('Add to Claude Code')}: claude mcp add --transport http marimo {mcp_url}"
    )
    if server_token is not None:
        print_tabbed(
            f"{_utf8('➜')}  {green('Add header')}: Marimo-Server-Token: {muted(server_token)}"
        )
    print_()


def print_pair_http_startup(mcp_url: str) -> None:
    """Print connection instructions for marimo pair --transport http."""
    print_()
    print_tabbed(f"{green('marimo pair', bold=True)} {_utf8('🤝')}")
    print_()
    print_tabbed(f"{_utf8('➜')}  {green('Add to Claude Code')}:")
    print_tabbed(f"      claude mcp add --transport http marimo {mcp_url}")
    print_()
    print_tabbed(
        f'{_utf8("💡")} To start pairing: claude -p "/marimo-pair on this notebook"'
    )
    print_()


def print_mcp_client(config: MCPConfig) -> None:
    keys = set(config.get("mcpServers", {}).keys()) | set(
        config.get("presets", [])
    )
    if len(keys) == 0:
        return

    print_tabbed(
        f"{_utf8('🌐')} {green('MCP servers', bold=True)}: {', '.join(keys)}"
    )
