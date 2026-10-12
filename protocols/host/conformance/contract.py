# Copyright 2026 Marimo. All rights reserved.
"""Wire validation and HTTP/SSE probes, independent of host implementations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import msgspec.yaml
from jsonschema import Draft202012Validator, FormatChecker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    import httpx

ROOT = Path(__file__).resolve().parent.parent
SPEC = msgspec.yaml.decode((ROOT / "openapi.yaml").read_bytes())
KINDS = (
    "host",
    "project",
    "notebook",
    "document",
    "cell",
    "runtime",
    "attachment",
    "run",
    "execution",
    "console",
    "display",
)


def validate(name: str, value: Any) -> None:
    schema = {
        "$ref": f"#/components/schemas/{name}",
        "components": SPEC["components"],
    }
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        value
    )


@dataclass
class Frame:
    event: str = "message"
    data: str = ""
    id: str | None = None
    comment: str | None = None

    def message(self) -> dict[str, Any]:
        value = json.loads(self.data)
        if self.event in ("ready", "reset"):
            assert value == {}, f"{self.event} must carry an empty object"
        elif self.event in KINDS:
            validate(f"{self.event.title()}Message", value)
        elif self.event.removesuffix(".removed") in KINDS:
            validate("RemovedMessage", value)
        return value


async def frames(lines: AsyncIterator[str]) -> AsyncIterator[Frame]:
    """Read SSE fields without inheriting ids across snapshot frames."""
    frame = Frame()
    data: list[str] = []
    async for line in lines:
        if not line:
            if data:
                frame.data = "\n".join(data)
                yield frame
            frame, data = Frame(), []
        elif line.startswith(":"):
            yield Frame(comment=line[1:].removeprefix(" "))
        else:
            field, separator, value = line.partition(":")
            value = value.removeprefix(" ") if separator else ""
            if field == "data":
                data.append(value)
            elif field == "event":
                frame.event = value or "message"
            elif field == "id" and "\0" not in value:
                frame.id = value


class Watch:
    def __init__(self, source: AsyncIterator[Frame], timeout: float):
        self.source = source
        self.timeout = timeout

    async def until(self, predicate: Callable[[Frame], bool]) -> list[Frame]:
        result: list[Frame] = []
        async with asyncio.timeout(self.timeout):
            async for frame in self.source:
                if frame.comment is None and (
                    frame.event in KINDS
                    or frame.event in ("ready", "reset")
                    or frame.event.removesuffix(".removed") in KINDS
                ):
                    frame.message()
                result.append(frame)
                if predicate(frame):
                    return result
        raise AssertionError("stream ended before the expected event")

    async def ready(self) -> list[Frame]:
        return await self.until(lambda frame: frame.event == "ready")


class Host:
    def __init__(self, client: httpx.AsyncClient, timeout: float):
        self.client = client
        self.timeout = timeout

    async def request(
        self, method: str, path: str, *, key: str | None = None, **kwargs: Any
    ) -> httpx.Response:
        headers = {"Idempotency-Key": key if key is not None else uuid4().hex}
        headers.update(kwargs.pop("headers", {}))
        async with asyncio.timeout(self.timeout):
            return await self.client.request(
                method, path.lstrip("/"), headers=headers, **kwargs
            )

    @asynccontextmanager
    async def watch(
        self, path: str = "/events", **kwargs: Any
    ) -> AsyncIterator[Watch]:
        # Bound response headers as well as each subsequent wait for events.
        context = self.client.stream("GET", path.lstrip("/"), **kwargs)
        async with asyncio.timeout(self.timeout):
            response = await context.__aenter__()
        try:
            assert response.status_code == 200
            assert (
                response.headers["content-type"].split(";")[0]
                == "text/event-stream"
            )
            assert "access-control-allow-origin" not in response.headers
            yield Watch(frames(response.aiter_lines()), self.timeout)
        finally:
            await context.__aexit__(None, None, None)

    async def snapshot(
        self, path: str = "/events", **kwargs: Any
    ) -> list[Frame]:
        async with self.watch(path, **kwargs) as watch:
            return await watch.ready()


def accepted(response: httpx.Response, status: int, schema: str) -> Any:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].split(";")[0] == "application/json"
    value = response.json()
    validate(schema, value)
    return value


def problem(response: httpx.Response, status: int, kind: str) -> Any:
    assert response.status_code == status, response.text
    assert (
        response.headers["content-type"].split(";")[0]
        == "application/problem+json"
    )
    value = response.json()
    validate("Problem", value)
    assert value["status"] == status
    assert value["type"] == f"tag:marimo.io,2026:host/{kind}"
    return value


def objects(snapshot: list[Frame], kind: str) -> list[dict[str, Any]]:
    return [frame.message()[kind] for frame in snapshot if frame.event == kind]


def etag(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def document_state(
    snapshot: list[Frame],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check document ordering and hashes using only observed wire records."""
    cells: dict[str, Any] = {}
    document = None
    for frame in snapshot:
        if frame.event == "cell":
            assert document is None, "cell arrived after the document"
            cell = frame.message()["cell"]
            assert cell["id"] not in cells, "duplicate cell in snapshot"
            cells[cell["id"]] = cell
        elif frame.event == "document":
            assert document is None, "duplicate document in snapshot"
            document = frame.message()["document"]
    assert document is not None, "snapshot has no document"
    assert sorted(document["order"]) == sorted(cells)
    for cell in cells.values():
        assert cell["notebook_id"] == document["id"]
        assert cell["code_hash"] == etag(cell["code"])
        config = cell["config"]
        parts = [cell["code_hash"], cell["name"]]
        parts.extend(
            json.dumps(config[key])
            for key in ("column", "disabled", "hide_code", "expand_output")
        )
        assert cell["etag"] == etag("\n".join(parts))
    assert document["order_etag"] == etag("\n".join(document["order"]))
    canonical = json.dumps(
        document["app_config"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert document["app_config_etag"] == etag(canonical)
    parts = [document["order_etag"], document["app_config_etag"]]
    parts.extend(cells[cell_id]["etag"] for cell_id in document["order"])
    assert document["etag"] == etag("\n".join(parts))
    return document, cells
