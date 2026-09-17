# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from unittest import mock

import pytest

from marimo._export.offline import _resolve_packages, bundle_wasm_runtime
from marimo._schemas.export_options import WASMRuntimeConfig
from marimo._utils.requests import Response


@pytest.fixture
def sources() -> WASMRuntimeConfig:
    return WASMRuntimeConfig(
        pyodide_index_url="https://runtime.example/",
        pyodide_lockfile_url="https://runtime.example/lock.json",
        pypi_index_url="https://packages.example/simple/",
    )


@pytest.fixture
def resolver():
    wheel = b"downloaded wheel"
    package = {
        "name": "example",
        "version": "1.0",
        "file_name": "https://wheels.example/example-1.0-py3-none-any.whl",
        "sha256": hashlib.sha256(wheel).hexdigest(),
        "depends": [],
        "imports": ["example"],
        "install_dir": "site",
    }
    lock = {"info": {"python": "3.14.0"}, "packages": {"example": package}}

    def fetch(url: str, **kwargs: object):
        del kwargs
        data = (
            json.dumps(lock).encode() if url.endswith("lock.json") else wheel
        )
        return Response(200, data, {})

    with (
        mock.patch("marimo._export.offline.requests.get", side_effect=fetch),
        mock.patch(
            "marimo._export.offline._resolve_packages",
            new_callable=mock.AsyncMock,
            return_value=lock,
        ) as resolve,
    ):
        yield resolve


@pytest.mark.asyncio
async def test_bundle_is_relocatable_and_preserves_source_config(
    tmp_path, sources, resolver
):
    code = '# /// script\n# dependencies = ["Example @ https://wheels.example/example-1.0-py3-none-any.whl", "Marimo==0.24.2"]\n# ///\nraise RuntimeError("must not execute")\n'
    rewritten, runtime = await bundle_wasm_runtime(
        code, tmp_path, sources=sources
    )
    assert "example==1.0" in rewritten
    assert "marimo==0.24.2" in rewritten
    assert 'raise RuntimeError("must not execute")' in rewritten
    assert (
        resolver.call_args.kwargs["package_base_url"]
        == sources.pyodide_index_url
    )
    assert (
        resolver.call_args.kwargs["pypi_index_url"] == sources.pypi_index_url
    )
    assert runtime.pyodide_index_url == "./pyodide/"
    assert runtime.pypi_index_url == "./packages/index/"
    assert runtime.pyodide_lockfile_url is not None
    lock_path = tmp_path / runtime.pyodide_lockfile_url
    lock = json.loads(lock_path.read_text())
    package = lock["packages"]["example"]
    assert (
        package["file_name"]
        == f"../packages/{package['sha256']}/example-1.0-py3-none-any.whl"
    )
    assert "https://" not in lock_path.read_text()
    wheel = tmp_path / "pyodide" / package["file_name"]
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == package["sha256"]
    index = tmp_path / "packages/index/example/index.html"
    assert (
        f"../../{package['sha256']}/example-1.0-py3-none-any.whl"
        in index.read_text()
    )
    assert sorted(p.name for p in (tmp_path / "pyodide").iterdir()) == [
        "pyodide.asm.mjs",
        "pyodide.asm.wasm",
        "pyodide.mjs",
        "python_stdlib.zip",
    ]
    assert not list(tmp_path.glob(".marimo-offline-*"))


@pytest.mark.asyncio
async def test_bad_checksum_preserves_existing_bundle(
    tmp_path, sources, resolver
):
    existing = tmp_path / "pyodide/pyodide.asm.wasm"
    existing.parent.mkdir()
    existing.write_bytes(b"previous runtime")
    resolver.return_value["packages"]["example"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Checksum mismatch"):
        await bundle_wasm_runtime("pass", tmp_path, sources=sources)
    assert existing.read_bytes() == b"previous runtime"
    assert not list(tmp_path.glob(".marimo-offline-*"))
    assert not (tmp_path / "lockfile").exists()


@pytest.mark.asyncio
async def test_each_notebook_keeps_its_wheel_contents(
    tmp_path, sources, resolver
):
    _, first = await bundle_wasm_runtime("one = 1", tmp_path, sources=sources)
    # Each resolver result is a fresh lockfile, like micropip.freeze().
    resolver.return_value["packages"]["example"]["file_name"] = (
        "https://wheels.example/example-1.0-py3-none-any.whl"
    )
    changed = b"different wheel with the same filename and version"
    resolver.return_value["packages"]["example"]["sha256"] = hashlib.sha256(
        changed
    ).hexdigest()
    with mock.patch(
        "marimo._export.offline.requests.get",
        return_value=Response(200, changed, {}),
    ) as fetch:
        fetch.side_effect = lambda url, **_kwargs: Response(
            200,
            json.dumps(resolver.return_value).encode()
            if url.endswith("lock.json")
            else changed,
            {},
        )
        _, second = await bundle_wasm_runtime(
            "one = 1", tmp_path, sources=sources
        )
    assert first.pyodide_lockfile_url != second.pyodide_lockfile_url
    for runtime, expected in [(first, b"downloaded wheel"), (second, changed)]:
        lock = json.loads(
            (tmp_path / runtime.pyodide_lockfile_url).read_text()
        )
        package = lock["packages"]["example"]
        assert (
            tmp_path / "pyodide" / package["file_name"]
        ).read_bytes() == expected


@pytest.mark.asyncio
async def test_cancelled_bundle_joins_downloads_before_cleanup(
    tmp_path, sources, resolver
):
    started = threading.Event()
    release = threading.Event()
    completed = []

    def download(url, target, checksum):
        del url, checksum
        started.set()
        assert release.wait(5)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"download")
        completed.append(target)
        return hashlib.sha256(b"download").hexdigest()

    with mock.patch("marimo._export.offline._download", side_effect=download):
        task = asyncio.create_task(
            bundle_wasm_runtime("pass", tmp_path, sources=sources)
        )
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    resolver.assert_not_called()
    assert len(completed) == 4
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["bootstrap", "imports"])
async def test_resolver_rejects_reported_package_failures(tmp_path, phase):
    pytest.importorskip("playwright.async_api")
    from marimo._export._html_asset_server import HtmlAssetServer
    from marimo._export.dependencies import _is_playwright_chromium_installed

    if not await _is_playwright_chromium_installed():
        pytest.skip("Chromium not installed")
    (tmp_path / "pyodide.mjs").write_text(
        "export async function loadPyodide() { return {"
        "globals: {set() {}}, runPythonAsync: async () => {}, runPython: () => false,"
        "loadPackage: async (_, callbacks) => {"
        + (
            'callbacks.errorCallback("bootstrap download failed");'
            if phase == "bootstrap"
            else ""
        )
        + "}, loadPackagesFromImports: async (_, callbacks) => {"
        + (
            'callbacks.errorCallback("imports download failed");'
            if phase == "imports"
            else ""
        )
        + "}};}"
    )
    with HtmlAssetServer(directory=tmp_path, route="/resolve.html") as server:
        server.set_html("<!doctype html>")
        with pytest.raises(Exception, match=f"{phase} download failed"):
            await _resolve_packages(
                "import numpy",
                page_url=server.page_url,
                index_url=server.base_url + "/",
                package_base_url=server.base_url + "/",
                lockfile={"info": {}, "packages": {}},
                pypi_index_url=None,
            )
