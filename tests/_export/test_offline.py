# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
from unittest import mock
from urllib.parse import urlparse

import pytest

from marimo._export.offline import (
    OfflineExportError,
    _fetch_in_python,
    _lock_required,
    _resolve_packages,
    bundle_wasm_runtime,
)
from marimo._pyodide.pyodide_constraints import PYODIDE_VERSION
from marimo._schemas.export_options import WASMRuntimeConfig
from marimo._utils import requests
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
        data = json.dumps(lock).encode() if "lock.json" in url else wheel
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
        resolver.call_args.kwargs["pypi_index_url"]
        == "https://packages.example/simple"
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
async def test_custom_pyodide_distribution_supplies_runtime_and_lockfile(
    tmp_path, resolver
):
    # Records the URLs requested from the resolver fixture's fake.
    with mock.patch.object(requests, "get", wraps=requests.get) as get:
        await bundle_wasm_runtime(
            "pass",
            tmp_path,
            sources=WASMRuntimeConfig(
                pyodide_index_url="https://mirror.example/pyodide"
            ),
        )
    assert sorted(call.args[0] for call in get.call_args_list) == [
        "https://mirror.example/pyodide/pyodide-lock.json",
        "https://mirror.example/pyodide/pyodide.asm.mjs",
        "https://mirror.example/pyodide/pyodide.asm.wasm",
        "https://mirror.example/pyodide/pyodide.mjs",
        "https://mirror.example/pyodide/python_stdlib.zip",
        "https://wheels.example/example-1.0-py3-none-any.whl",
    ]
    assert (
        resolver.call_args.kwargs["package_base_url"]
        == "https://mirror.example/pyodide/"
    )


@pytest.mark.asyncio
async def test_default_sources_are_the_hosted_distribution(tmp_path, resolver):
    with mock.patch.object(requests, "get", wraps=requests.get) as get:
        await bundle_wasm_runtime(
            "pass", tmp_path, sources=WASMRuntimeConfig()
        )
    assert {
        urlparse(call.args[0]).hostname for call in get.call_args_list
    } == {
        "cdn.jsdelivr.net",
        "wasm.marimo.app",
        "wheels.example",
    }
    assert resolver.call_args.kwargs["pypi_index_url"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            Response(404, b"missing", {}),
            "Could not download https://runtime.example/lock.json",
        ),
        (
            Response(200, b"<!doctype html>", {}),
            "https://runtime.example/lock.json is not a Pyodide lockfile",
        ),
    ],
)
async def test_lockfile_failures_name_the_source_url(
    tmp_path, sources, resolver, response, message
):
    with (
        mock.patch.object(requests, "get", return_value=response),
        pytest.raises(OfflineExportError, match=re.escape(message)),
    ):
        await bundle_wasm_runtime("pass", tmp_path, sources=sources)
    resolver.assert_not_called()


def _package(name: str, *depends: str) -> dict[str, object]:
    return {
        "name": name,
        "version": "1.0",
        "file_name": f"{name}-1.0-py3-none-any.whl",
        "sha256": None,
        "depends": list(depends),
    }


def test_bundle_keeps_the_dependency_closure_of_required_packages():
    lockfile = {
        "info": {"python": "3.14.0"},
        "packages": {
            "marimo-base": _package("marimo", "msgspec"),
            "msgspec": _package("msgspec"),
            "numpy": _package("numpy"),
        },
    }
    # Pyodide reports hosted marimo-base under its lockfile name, marimo.
    assert _lock_required(
        {"lockfile": lockfile, "required": ["Marimo_Base"]}
    ) == {
        "info": {"python": "3.14.0"},
        "packages": {
            "marimo-base": _package("marimo", "msgspec"),
            "msgspec": _package("msgspec"),
        },
    }


def test_bundle_rejects_packages_missing_from_the_resolution():
    lockfile = {"info": {}, "packages": {"black": _package("black", "click")}}
    with pytest.raises(
        OfflineExportError, match="No resolved package is named click"
    ):
        _lock_required({"lockfile": lockfile, "required": ["black"]})


@pytest.mark.asyncio
async def test_page_requests_are_fetched_in_python_with_cors():
    route = mock.AsyncMock()
    route.request.url = "https://mirror.example/simple/humanize/"
    route.request.headers = {"accept": "application/vnd.pypi.simple.v1+json"}
    page = Response(200, b"<a>", {"Content-Type": "text/html"})
    with mock.patch.object(requests, "get", return_value=page) as get:
        await _fetch_in_python(route)
    get.assert_called_once_with(
        "https://mirror.example/simple/humanize/",
        headers={"Accept": "application/vnd.pypi.simple.v1+json"},
        timeout=60,
    )
    route.fulfill.assert_awaited_once_with(
        status=200,
        body=b"<a>",
        headers={
            "access-control-allow-origin": "*",
            "content-type": "text/html",
        },
    )


@pytest.mark.asyncio
async def test_failed_page_requests_are_aborted():
    route = mock.AsyncMock()
    route.request.url = "https://mirror.example/simple/humanize/"
    route.request.headers = {}
    with mock.patch.object(
        requests, "get", side_effect=ConnectionResetError("reset")
    ):
        await _fetch_in_python(route)
    route.abort.assert_awaited_once_with()
    route.fulfill.assert_not_awaited()


@pytest.mark.asyncio
async def test_bundle_rejects_package_names_outside_the_index(
    tmp_path, sources, resolver
):
    from packaging.requirements import InvalidRequirement

    packages = resolver.return_value["packages"]
    packages["../../escape"] = packages.pop("example")
    with pytest.raises(InvalidRequirement):
        await bundle_wasm_runtime("pass", tmp_path, sources=sources)
    assert list(tmp_path.iterdir()) == []


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


async def _resolve_with_stub(
    tmp_path, *, version=PYODIDE_VERSION, load_package="", load_imports=""
):
    """Run the resolver against a stub `pyodide.mjs` served next to the page."""
    pytest.importorskip("playwright.async_api")
    from marimo._export._html_asset_server import HtmlAssetServer
    from marimo._export.dependencies import _is_playwright_chromium_installed

    if not await _is_playwright_chromium_installed():
        pytest.skip("Chromium not installed")
    (tmp_path / "pyodide.mjs").write_text(
        f"export const version = {json.dumps(version)};"
        "export async function loadPyodide() { return {"
        "globals: {set() {}}, loadedPackages: {}, runPythonAsync: async () => {},"
        "runPython: code => ({'micropip.freeze()': '{\"info\": {}, \"packages\": {}}',"
        "'json.dumps(required)': '[]'})[code] ?? false,"
        f"loadPackage: async (_, callbacks) => {{ {load_package} }},"
        f"loadPackagesFromImports: async (_, callbacks) => {{ {load_imports} }},"
        "};}"
    )
    with HtmlAssetServer(directory=tmp_path, route="/resolve.html") as server:
        server.set_html("<!doctype html>")
        return await asyncio.wait_for(
            _resolve_packages(
                "import numpy",
                page_url=server.page_url,
                index_url=server.base_url + "/",
                package_base_url=server.base_url + "/",
                lockfile={"info": {}, "packages": {}},
                pypi_index_url=None,
            ),
            timeout=60,
        )


def _load_from(url: str) -> str:
    return (
        f"const response = await fetch({json.dumps(url)}).catch(() => null);"
        'if (!response?.ok) callbacks.errorCallback("mirror unavailable");'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["bootstrap", "imports"])
async def test_resolver_rejects_reported_package_failures(tmp_path, phase):
    failure = f'callbacks.errorCallback("{phase} download failed");'
    with pytest.raises(Exception, match=f"{phase} download failed"):
        await _resolve_with_stub(
            tmp_path,
            load_package=failure if phase == "bootstrap" else "",
            load_imports=failure if phase == "imports" else "",
        )


@pytest.mark.asyncio
async def test_resolver_rejects_other_pyodide_versions(tmp_path):
    expected = (
        f"serves Pyodide 0.0.0, but marimo needs Pyodide {PYODIDE_VERSION}"
    )
    with pytest.raises(Exception, match=re.escape(expected)):
        await _resolve_with_stub(tmp_path, version="0.0.0")


@pytest.mark.asyncio
async def test_resolver_loads_packages_from_mirrors_without_cors(tmp_path):
    from marimo._export._html_asset_server import HtmlAssetServer

    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "package.whl").write_bytes(b"wheel")
    # SimpleHTTPRequestHandler sends no Access-Control-Allow-Origin header.
    with HtmlAssetServer(directory=mirror, route="/unused") as server:
        resolved = await _resolve_with_stub(
            tmp_path, load_package=_load_from(f"{server.base_url}/package.whl")
        )
    assert resolved == {"info": {}, "packages": {}}


@pytest.mark.asyncio
async def test_resolver_fails_fast_when_mirror_connections_fail(tmp_path):
    # Holding the port avoids reuse races, and closing each connection fails
    # the request at once on every platform.
    mirror = await asyncio.start_server(
        lambda _reader, writer: writer.close(), "127.0.0.1", 0
    )
    port = mirror.sockets[0].getsockname()[1]
    async with mirror:
        with pytest.raises(Exception, match="mirror unavailable"):
            await _resolve_with_stub(
                tmp_path,
                load_package=_load_from(
                    f"http://127.0.0.1:{port}/package.whl"
                ),
            )
