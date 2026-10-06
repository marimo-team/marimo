# Copyright 2026 Marimo. All rights reserved.
"""Run with MARIMO_TEST_SCREENSHOTS=1 after building the frontend.

The Playwright CI job supplies built assets and matching Chromium binaries.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import signal
import socket
import sys
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.async_api import Page, WebSocket


async def _execute(
    client: httpx.AsyncClient,
    session_id: str,
    code: str,
    *,
    verify_png: bool = False,
) -> str:
    response = await client.post(
        "/api/kernel/execute",
        headers={"Marimo-Session-Id": session_id},
        json={"code": code},
        timeout=90,
    )
    response.raise_for_status()
    event = ""
    stdout = ""
    stderr = ""
    completed = False
    for line in response.text.splitlines():
        if line.startswith("event: "):
            event = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data = json.loads(line.removeprefix("data: "))
            if event == "stdout":
                stdout += data["data"]
            elif event == "stderr":
                stderr += data["data"]
            elif event == "done":
                assert data["success"], stderr
                if verify_png:
                    assert data["output"]["mimetype"] == "image/png"
                    image_url = data["output"]["data"]
                    assert image_url.startswith("data:image/png;base64,")
                    png = base64.b64decode(
                        image_url.split(",", 1)[1], validate=True
                    )
                    assert png.startswith(b"\x89PNG\r\n\x1a\n")
                    assert (
                        "PNG_SHA=" + hashlib.sha256(png).hexdigest() in stdout
                    )
                completed = True
    assert completed, response.text
    return stdout.strip()


@pytest.mark.integration
@pytest.mark.timeout(180)
@pytest.mark.skipif(
    os.environ.get("MARIMO_TEST_SCREENSHOTS") != "1",
    reason="Requires built frontend assets and Playwright Chromium",
)
async def test_screenshots_attach_to_live_notebook(tmp_path: Path) -> None:
    from playwright.async_api import async_playwright

    token = "screenshot-test+&=#?"
    token_file = tmp_path / "token.txt"
    token_file.write_text(token)
    token_file.chmod(0o600)
    files = [tmp_path / "Notebook A + & # ?.py", tmp_path / "Notebook B.py"]
    for file in files:
        file.write_text(
            "import marimo\napp = marimo.App()\n"
            "@app.cell\ndef _():\n    value = 1\n    return (value,)\n"
            "if __name__ == '__main__':\n    app.run()\n"
        )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}/capture-check"
    log_path = tmp_path / "server.log"
    with log_path.open("w") as log:
        server = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "marimo",
            "edit",
            str(tmp_path),
            "--headless",
            "--no-sandbox",
            "--skip-update-check",
            "--port",
            str(port),
            "--base-url",
            "/capture-check",
            "--token-password-file",
            str(token_file),
            stdout=log,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            async with httpx.AsyncClient(
                base_url=base + "/",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        response = await client.get("/api/sessions")
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert server.returncode is None, log_path.read_text()
                    assert time.monotonic() < deadline, log_path.read_text()
                    await asyncio.sleep(0.1)
                async with httpx.AsyncClient() as anonymous:
                    assert (
                        await anonymous.get(base + "/api/sessions")
                    ).status_code != 200

                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch()
                    keys = [str(file) for file in files] + [
                        "__new__capture-test"
                    ]
                    editors: list[tuple[str, Page, WebSocket, str]] = []
                    for key in keys:
                        context = await browser.new_context()
                        page = await context.new_page()
                        sockets: list[WebSocket] = []
                        page.on(
                            "websocket",
                            lambda ws, records=sockets: records.append(ws),
                        )
                        await page.goto(
                            base
                            + "/?"
                            + urlencode({"file": key, "access_token": token})
                        )
                        deadline = time.monotonic() + 30
                        while (
                            not sockets
                            or parse_qs(urlsplit(sockets[0].url).query)[
                                "session_id"
                            ][0]
                            not in (await client.get("/api/sessions")).json()
                        ):
                            assert time.monotonic() < deadline
                            await asyncio.sleep(0.1)
                        session_id = parse_qs(urlsplit(sockets[0].url).query)[
                            "session_id"
                        ][0]
                        editors.append((key, page, sockets[0], session_id))
                    sessions_before = (
                        await client.get("/api/sessions")
                    ).json()
                    assert len(sessions_before) == 3
                    for index, (key, page, websocket, session_id) in enumerate(
                        editors
                    ):
                        marker = f"LIVE NOTEBOOK {index}"
                        source = f"import marimo as mo\nmo.Html('<div>{marker}</div>')"
                        if index == 2:
                            operation = (
                                f"cell_id = ctx.create_cell({source!r})"
                            )
                        else:
                            operation = (
                                "cell_id = ctx.cells[-1].id\n"
                                "    previous_code = ctx.cells[cell_id].code\n"
                                f"    ctx.edit_cell(cell_id, code={source!r})"
                            )
                        # Keep the same context: its empty snapshot must not
                        # prevent capturing output rendered after run_cell.
                        code = f"""
import marimo._code_mode as cm
from marimo._code_mode.screenshot import ScreenshotError
import time
from urllib.parse import parse_qs, urlsplit
ctx = cm.get_context()
assert all(cell.output is None or cell.output.data == "" for cell in ctx.cells)
empty_id = ctx.cells[-1].id
async with ctx:
    ctx.run_cell(empty_id)
for attempt in range(2):
    started = time.monotonic()
    try:
        await ctx.screenshot(empty_id)
    except ScreenshotError as error:
        assert "has no rendered output" in str(error), str(error)
        assert "ctx.run_cell" in str(error)
    else:
        raise AssertionError("An assignment has no display output")
    if attempt:
        elapsed = time.monotonic() - started
        assert elapsed < 5
        print("EMPTY_CAPTURE_MS=" + str(round(elapsed * 1000)))
async with ctx:
    {operation}
    ctx.run_cell(cell_id)
image = await ctx.screenshot(cell_id)
session = ctx._screenshot_session
assert image.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
assert {marker!r} in await session._page.locator("#output-" + cell_id).inner_text()
assert parse_qs(urlsplit(session._page.url).query)["file"] == [{key!r}]
assert parse_qs(urlsplit(session._page.url).query)["kiosk"] == ["true"]
assert parse_qs(urlsplit(session._page.url).query)["capture"] == ["true"]
assert await session._page.locator("[data-cell-output-id]").count() > 0
browser = session._browser
page = session._page
await ctx.close_screenshot_session()
assert not browser.is_connected()
assert page.is_closed()

# A bound, non-listening port makes real Chromium navigation fail.
import socket
from playwright.async_api import Error
with socket.socket() as unavailable:
    unavailable.bind(("127.0.0.1", 0))
    session._server_url = "http://127.0.0.1:" + str(unavailable.getsockname()[1])
    try:
        await session.capture(cell_id)
    except Error as error:
        assert "net::ERR_CONNECTION_" in str(error)
    else:
        raise AssertionError("Navigation should fail")
assert session._page is None
assert session._browser is None
assert session._playwright is None
session._server_url = {base!r}
retry_image = await session.capture(cell_id)
assert retry_image.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
assert {marker!r} in await session._page.locator("#output-" + cell_id).inner_text()
await session.close()
import hashlib
print("PNG_SHA=" + hashlib.sha256(image).hexdigest())
print("CELL_ID=" + cell_id)
image
"""
                        stdout = await _execute(
                            client, session_id, code, verify_png=True
                        )
                        empty_capture_ms = next(
                            line.removeprefix("EMPTY_CAPTURE_MS=")
                            for line in stdout.splitlines()
                            if line.startswith("EMPTY_CAPTURE_MS=")
                        )
                        print(
                            f"Reused empty-output capture: {empty_capture_ms}ms"

                        )
                        cell_id = next(
                            line.removeprefix("CELL_ID=")
                            for line in stdout.splitlines()
                            if line.startswith("CELL_ID=")
                        )
                        await page.get_by_text(marker, exact=True).wait_for()
                        kiosk = await page.context.new_page()
                        await kiosk.goto(
                            base
                            + "/?"
                            + urlencode(
                                {
                                    "file": key,
                                    "access_token": token,
                                    "kiosk": "true",
                                }
                            )
                        )
                        await kiosk.get_by_text(marker, exact=True).wait_for()
                        assert (
                            await kiosk.locator(
                                "[data-cell-output-id]"
                            ).count()
                            == 0
                        )
                        await kiosk.close()
                        assert not websocket.is_closed()
                        assert (
                            await _execute(
                                client, session_id, "print('still connected')"
                            )
                            == "still connected"
                        )
                        assert (
                            await page.locator("#output-" + cell_id).count()
                            == 1
                        )
                    assert set(sessions_before) == set(
                        (await client.get("/api/sessions")).json()
                    )
                    await browser.close()
        finally:
            if server.returncode is None:
                os.killpg(server.pid, signal.SIGINT)
                try:
                    await asyncio.wait_for(server.wait(), timeout=15)
                except TimeoutError:
                    os.killpg(server.pid, signal.SIGKILL)
                    await asyncio.wait_for(server.wait(), timeout=5)


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("MARIMO_TEST_SCREENSHOTS") != "1",
    reason="Requires Playwright Chromium",
)
async def test_screenshot_waits_for_frontend_state_and_rendering() -> None:
    from playwright.async_api import (
        TimeoutError as BrowserTimeoutError,
        async_playwright,
    )

    from marimo._code_mode.screenshot import _ScreenshotSession
    from marimo._types.ids import CellId_t

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            session = _ScreenshotSession("http://localhost:1234")
            session._page = page
            for state in ("unknown", "pending", "available"):
                content = "old output" if state != "available" else ""
                await page.set_content(
                    f'<span hidden data-cell-output-id="a" data-output-state="{state}"></span>'
                    f'<div id="output-a">{content}</div>'
                )
                with pytest.raises(BrowserTimeoutError):
                    await session._wait_for_output(CellId_t("a"), timeout=50)
                await page.evaluate("""() => {
                    document.querySelector('[data-cell-output-id]').dataset.outputState = 'available';
                    document.getElementById('output-a').textContent = 'new output';
                }""")
                assert (
                    await session._wait_for_output(CellId_t("a"), timeout=1000)
                    == "ready"
                )

            await page.evaluate("""() => {
                document.querySelector('[data-cell-output-id]').dataset.outputState = 'pending';
            }""")
            wait = asyncio.create_task(
                session._wait_for_output(CellId_t("a"), timeout=1000)
            )
            await page.evaluate("""() => {
                document.querySelector('[data-cell-output-id]').dataset.outputState = 'empty';
            }""")
            assert await wait == "empty"

            # Older frontend assets have no marker but can still render output.
            await page.set_content('<div id="output-a">rich output</div>')
            assert (
                await session._wait_for_output(CellId_t("a"), timeout=1000)
                == "ready"
            )
        finally:
            await browser.close()
