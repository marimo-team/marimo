# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from typing import Optional

from marimo._cli.print import bold, green, muted
from marimo._server.utils import print_, print_tabbed

UTF8_SUPPORTED = False

try:
    "🌊🍃".encode(sys.stdout.encoding)
    UTF8_SUPPORTED = True
except Exception:
    pass


def print_startup(
    *, file_name: Optional[str], url: str, run: bool, new: bool, network: bool
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
        print_tabbed(
            f"{_utf8('➜')}  {green('Network')}: {_colorized_url(_get_network_url(url))}"
        )
    print_()


def print_shutdown() -> None:
    print_()
    print_tabbed("\033[32mThanks for using marimo!\033[0m %s" % _utf8("🌊🍃"))
    print_()


def _get_network_url(url: str) -> str:
    import socket

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

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

    url_string = f"{url.scheme}://{url.hostname}"
    # raw https and http urls do not have a port to parse
    if url.port:
        url_string += f":{url.port}"

    return bold(
        f"{url_string}{url.path}{query}",
    )


def _utf8(msg: str) -> str:
    return msg if UTF8_SUPPORTED else ""
