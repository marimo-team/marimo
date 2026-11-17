#!/usr/bin/env python3
"""Inspect a local marimo host through its event stream.

Usage:
  uv run scripts/host_events.py events --url URL [options]
  uv run scripts/host_events.py snapshot --url URL [options]

  events     Print one JSON object per event until disconnect or Ctrl-C.
  snapshot   Read the stream through `ready`, print `{cursor, events}`, exit.

Options:
  --url URL       Local edit server URL. Required.
  --notebook ID   Select one notebook instead of the host catalog.
  --types KINDS   Comma-separated event kinds. The server validates them.
  --pretty        Indent JSON and color it in supported terminals.

Authentication uses the private local host record, as `marimo pair` does.
A notebook stream creates a client attachment while it is open. The host
catalog stream does not. A snapshot contains current records only, never
custom occurrences or control messages. Its cursor resumes the stream.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
from contextlib import closing
from typing import TYPE_CHECKING
from urllib.parse import quote, urlencode
from uuid import uuid4

from marimo._cli.pair.client import (
    PairError,
    SSEEvent,
    iter_sse,
    open_response,
    resolve_host,
)
from marimo._cli.print import _supports_color
from marimo._server.host import (
    ATTACHMENT_IDENTITY,
    ATTACHMENT_KIND,
    ATTACHMENT_NAME,
)
from marimo._server.host.stream_options import OBJECT_TYPES

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

RECORD_KINDS = OBJECT_TYPES - {"custom"}


def stream_url(base: str, *, notebook: str | None, types: str | None) -> str:
    path = "/events"
    if notebook is not None:
        path = f"/notebooks/{quote(notebook, safe='')}{path}"
    url = base.rstrip("/") + path
    if types is not None:
        url += "?" + urlencode({"types": types}, safe=",")
    return url


def stream_headers(
    token: str, *, notebook: str | None, name: str
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if notebook is not None:
        headers[ATTACHMENT_IDENTITY] = str(uuid4())
        headers[ATTACHMENT_KIND] = "client"
        headers[ATTACHMENT_NAME] = name
    return headers


def frame(event: SSEEvent) -> dict[str, object]:
    payload: dict[str, object] = {
        "event": event.name,
        "data": json.loads(event.data),
    }
    if event.id is not None:
        payload["id"] = event.id
    return payload


def json_formatter(pretty: bool) -> Callable[[object], str]:
    indent = 2 if pretty else None
    use_color = (
        pretty
        and not os.environ.get("NO_COLOR")
        and sys.stdout.isatty()
        and _supports_color()
    )
    if not use_color:
        return lambda payload: json.dumps(payload, indent=indent)

    from pygments import highlight
    from pygments.formatters import TerminalFormatter
    from pygments.lexers import JsonLexer

    lexer = JsonLexer()
    formatter = TerminalFormatter()

    def format_payload(payload: object) -> str:
        output = json.dumps(payload, indent=indent)
        return highlight(output, lexer, formatter).rstrip("\n")

    return format_payload


def parse_types(value: str | None) -> str | None:
    if value is None:
        return None
    kinds = [kind.strip() for kind in value.split(",")]
    if not all(kinds):
        raise SystemExit("--types must not contain empty entries.")
    return ",".join(dict.fromkeys(kinds))


def print_events(
    events: Iterator[SSEEvent],
    format_payload: Callable[[object], str],
    pretty: bool,
) -> None:
    first = True
    for event in events:
        if pretty and not first:
            print()
        print(format_payload(frame(event)), flush=True)
        first = False


def print_snapshot(
    events: Iterator[SSEEvent], format_payload: Callable[[object], str]
) -> None:
    records: list[dict[str, object]] = []
    for event in events:
        if event.name == "reset":
            records = []
        elif event.name == "ready":
            if not event.id:
                raise SystemExit("The ready event is missing its cursor.")
            print(format_payload({"cursor": event.id, "events": records}))
            return
        elif event.name in RECORD_KINDS:
            records.append(frame(event))
    raise SystemExit("The stream ended before ready. No snapshot was printed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=("events", "snapshot"))
    parser.add_argument("--url", required=True)
    parser.add_argument("--notebook")
    parser.add_argument("--types")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    types = parse_types(args.types)
    format_payload = json_formatter(args.pretty)
    try:
        host = resolve_host(args.url)
        response = open_response(
            method="GET",
            url=stream_url(host.url, notebook=args.notebook, types=types),
            headers=stream_headers(
                host.token,
                notebook=args.notebook,
                name=f"host_events {args.command}",
            ),
            body=None,
            read_timeout=None,
        )
    except PairError as error:
        print(error, file=sys.stderr)
        return 1

    with closing(response):
        try:
            events = iter_sse(response)
            if args.command == "snapshot":
                print_snapshot(events, format_payload)
            else:
                print_events(events, format_payload, args.pretty)
        except KeyboardInterrupt:
            return 130
        except BrokenPipeError:
            # Python flushes stdout again at exit. Point it at devnull so the
            # second flush does not fail after the reader closed the pipe.
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            return 0
        except (OSError, http.client.HTTPException):
            print("The event stream was disconnected.", file=sys.stderr)
            return 1
        except ValueError:
            print("The event stream contained invalid JSON.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
