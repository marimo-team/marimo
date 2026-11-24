# Copyright 2026 Marimo. All rights reserved.
"""Record the editor's WebSocket traffic from a running `marimo edit` server.

Connects to `/ws` the way the frontend does, records every frame until the
stream goes quiet, and prints messages and bytes per event kind, the bytes
that crossed the socket, and when the session's milestones arrived.

Usage:

    marimo edit notebook.py --headless --no-token --port 2718
    python scripts/benchmarks/ws_traffic.py http://127.0.0.1:2718 \
        --expect-run --out trace.jsonl

`--expect-run` waits for a run to complete, for a first connection with
`runtime.auto_instantiate` on. Reuse `--session-id` to reconnect, pass
`--cursor` to resume, and `--no-deflate` to decline `permessage-deflate`,
which browsers always offer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from websockets.asyncio.client import connect


class CountingSocket(socket.socket):
    """A socket that counts the bytes it receives, as compressed on the wire."""

    received = 0

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        data = super().recv(bufsize, flags)
        self.received += len(data)
        return data


def kind_of(message: dict[str, Any]) -> str:
    kind = str(message.get("event"))
    data = message.get("data") or {}
    if kind == "marimo":
        return f"marimo:{data['marimo']['op']}"
    if kind in ("execution", "run"):
        return f"{kind}:{data[kind]['state']['status']}"
    return kind


async def record(
    args: argparse.Namespace,
) -> tuple[list[tuple[float, str]], int, str]:
    base = urlsplit(args.url)
    assert base.hostname is not None
    assert base.port is not None
    query = {"query_params": "", "session_id": args.session_id}
    if args.cursor:
        query["cursor"] = args.cursor
    if args.kiosk:
        query["kiosk"] = "true"
    uri = f"ws://{base.netloc}{base.path.rstrip('/')}/ws?{urlencode(query)}"

    sock = CountingSocket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((base.hostname, base.port))
    sock.setblocking(False)
    frames: list[tuple[float, str]] = []
    open_runs: set[str] = set()
    runs_completed = 0
    start = time.perf_counter()
    async with connect(
        uri,
        sock=sock,
        max_size=None,
        compression=None if args.no_deflate else "deflate",
    ) as ws:
        assert ws.response is not None
        extensions = ws.response.headers.get("Sec-WebSocket-Extensions", "")
        while time.perf_counter() - start < args.timeout:
            try:
                frame = await asyncio.wait_for(ws.recv(), args.idle)
            except TimeoutError:
                if not open_runs and (runs_completed or not args.expect_run):
                    break
                continue
            assert isinstance(frame, str)
            frames.append((time.perf_counter() - start, frame))
            message = json.loads(frame)
            if message.get("event") == "run":
                run = message["data"]["run"]
                if run["state"]["status"] == "completed":
                    open_runs.discard(run["id"])
                    runs_completed += 1
                else:
                    open_runs.add(run["id"])
    return frames, sock.received, extensions


def report(
    frames: list[tuple[float, str]], wire_bytes: int, extensions: str
) -> None:
    counts: dict[str, int] = defaultdict(int)
    sizes: dict[str, int] = defaultdict(int)
    largest: dict[str, int] = defaultdict(int)
    first: dict[str, float] = {}
    last: dict[str, float] = {}
    for at, frame in frames:
        kind = kind_of(json.loads(frame))
        size = len(frame.encode())
        counts[kind] += 1
        sizes[kind] += size
        largest[kind] = max(largest[kind], size)
        first.setdefault(kind, at)
        last[kind] = at

    total = sum(sizes.values())
    print(f"extensions: {extensions or '(none)'}")
    print(f"{'kind':34} {'count':>7} {'bytes':>11} {'%':>6} {'max':>9}")
    for kind in sorted(sizes, key=lambda k: -sizes[k]):
        print(
            f"{kind:34} {counts[kind]:7d} {sizes[kind]:11d} "
            f"{100 * sizes[kind] / total:6.1f} {largest[kind]:9d}"
        )
    print(f"{'total':34} {len(frames):7d} {total:11d}")
    print(
        f"wire bytes received: {wire_bytes} ({100 * wire_bytes / total:.1f}%)"
    )
    print("milestones (ms since connect):")
    for label, kind, times in (
        ("ready", "ready", first),
        ("kernel-ready", "marimo:kernel-ready", first),
        ("first output", "output", first),
        ("last execution completed", "execution:completed", last),
        ("completed-run", "marimo:completed-run", last),
    ):
        if kind in times:
            print(f"  {label:26} {1000 * times[kind]:9.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("url", help="server URL, e.g. http://127.0.0.1:2718")
    parser.add_argument("--out", type=Path, help="write frames as JSON lines")
    parser.add_argument("--session-id", default=f"s_{uuid4().hex[:6]}")
    parser.add_argument("--cursor", help="resume after this event id")
    parser.add_argument("--kiosk", action="store_true")
    parser.add_argument("--no-deflate", action="store_true")
    parser.add_argument("--expect-run", action="store_true")
    parser.add_argument("--idle", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    frames, wire_bytes, extensions = asyncio.run(record(args))
    if args.out is not None:
        with args.out.open("w") as output:
            for at, frame in frames:
                output.write(json.dumps({"t": at, "frame": frame}) + "\n")
    report(frames, wire_bytes, extensions)


if __name__ == "__main__":
    main()
