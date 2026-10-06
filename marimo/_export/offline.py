# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
from urllib.parse import quote, unquote, urljoin, urlparse

from marimo._environments import script_metadata
from marimo._export._html_asset_server import HtmlAssetServer
from marimo._pyodide.pyodide_constraints import PYODIDE_VERSION
from marimo._schemas.export_options import WASMRuntimeConfig
from marimo._utils import requests
from marimo._utils.inline_script_metadata import PyProjectReader
from marimo._version import __version__

if TYPE_CHECKING:
    from playwright.async_api import Route  # type: ignore[import-not-found]


class OfflineExportError(RuntimeError):
    """The runtime or package bundle could not be prepared."""


class _Package(TypedDict):
    name: str
    version: str
    file_name: str
    sha256: str | None
    depends: list[str]


class _Lockfile(TypedDict):
    info: dict[str, str]
    packages: dict[str, _Package]


_RESOLVE_PACKAGES = r"""async ({ indexURL, packageBaseUrl, lockfile, pypiIndexUrl, pyodideVersion, marimoVersion, code, requirements }) => {
    const { loadPyodide, version } = await import(indexURL + "pyodide.mjs");
    // The exported page loads this runtime with the frontend's Pyodide API.
    if (version !== pyodideVersion) {
        throw new Error(`${packageBaseUrl} serves Pyodide ${version}, but marimo needs Pyodide ${pyodideVersion}.`);
    }
    const pyodide = await loadPyodide({ indexURL, packageBaseUrl, lockFileContents: lockfile });
    const errors = [];
    const callbacks = { errorCallback: message => errors.push(message) };
    await pyodide.loadPackage(
        ["micropip", "packaging", "docutils", "pygments", "jedi", "pyodide-http"],
        callbacks,
    );
    if (errors.length) throw new Error(errors.join("\n"));
    pyodide.globals.set("requirements_json", JSON.stringify(requirements));
    pyodide.globals.set("index_url", pypiIndexUrl);
    pyodide.globals.set("base_url", location.href);
    pyodide.globals.set("marimo_version", marimoVersion);
    await pyodide.runPythonAsync(`
import json
import micropip
import micropip.package_index
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from urllib.parse import urljoin

if index_url:
    micropip.set_index_urls(index_url)
    # micropip checks pyodide-lock.json first only for its default index. Keep
    # that order for mirrors so Pyodide-built pins such as pydantic-core hold.
    micropip.package_index.DEFAULT_INDEX_URLS[:] = [index_url]
# Stock Pyodide lockfiles lack marimo's packages, so micropip may use the index.
await micropip.install([f"marimo-base=={marimo_version}", "black"])
required = ["marimo-base", "black"]
requirements = []
for value in json.loads(requirements_json):
    requirement = Requirement(value)
    if requirement.marker and not requirement.marker.evaluate():
        continue
    if canonicalize_name(requirement.name) == "marimo":
        requirement.name = "marimo-base"
    if requirement.url:
        requirement.url = urljoin(base_url, requirement.url)
    requirements.append(str(requirement))
    required.append(canonicalize_name(requirement.name))
await micropip.install(requirements)
`);
    // Keep the same SQL dependency policy as shouldLoadDuckDBPackages.
    const usesDuckDB = /(^|\n)\s*(?:import\s+[^\n#]*\bduckdb\b|from\s+duckdb\b|[^\n#]*\bduckdb\s*\.)/.test(code);
    if (code.includes("mo.sql") || usesDuckDB || pyodide.runPython('"duckdb" in required')) {
        code += "\nimport duckdb, pandas";
        if (code.includes("polars")) code += "\nimport pyarrow";
        await pyodide.runPythonAsync('await micropip.install("sqlglot")\nrequired.append("sqlglot")');
    }
    await pyodide.loadPackagesFromImports(code, callbacks);
    if (errors.length) throw new Error(errors.join("\n"));
    return {
        lockfile: JSON.parse(pyodide.runPython("micropip.freeze()")),
        required: [...Object.keys(pyodide.loadedPackages), ...JSON.parse(pyodide.runPython("json.dumps(required)"))],
    };
}"""


class _Resolution(TypedDict):
    lockfile: _Lockfile
    required: list[str]


def _lock_required(resolution: _Resolution) -> _Lockfile:
    """Keep the lockfile entries in the dependency closure of `required`.

    micropip only logs lockfile packages that fail to download, so the bundle
    follows what the notebook needs rather than what loaded in the browser.
    """
    from packaging.utils import canonicalize_name

    available = resolution["lockfile"]["packages"]
    # Pyodide reports loaded packages by entry name, which can differ from the
    # key: marimo's hosted lockfile names its marimo-base entry "marimo".
    keys = {
        canonicalize_name(package["name"]): key
        for key, package in available.items()
    }
    packages: dict[str, _Package] = {}
    pending = list(resolution["required"])
    while pending:
        name = canonicalize_name(pending.pop())
        key = name if name in available else keys.get(name)
        if key is None:
            raise OfflineExportError(
                f"No resolved package is named {name}. Check that direct "
                "references use the wheel's project name."
            )
        if key in packages:
            continue
        packages[key] = available[key]
        pending.extend(packages[key]["depends"])
    return {"info": resolution["lockfile"]["info"], "packages": packages}


def _fetch(url: str) -> bytes:
    try:
        return requests.get(url, timeout=60).raise_for_status().content
    except (requests.RequestError, OSError) as error:
        raise OfflineExportError(
            f"Could not download {url}: {error}"
        ) from error


def _download(url: str, target: Path, sha256: str | None = None) -> str:
    data = _fetch(url)
    digest = hashlib.sha256(data).hexdigest()
    if sha256 and digest != sha256:
        raise ValueError(f"Checksum mismatch for {url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return digest


def _download_files(
    files: dict[Path, tuple[str, str | None]],
) -> dict[Path, str]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = {
            target: pool.submit(_download, url, target, checksum)
            for target, (url, checksum) in files.items()
        }
        return {target: future.result() for target, future in pending.items()}


async def _download_all(
    files: dict[Path, tuple[str, str | None]],
) -> dict[Path, str]:
    task = asyncio.create_task(asyncio.to_thread(_download_files, files))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Threads cannot be cancelled. Join them before staging is cleaned up.
        with suppress(Exception):
            await asyncio.shield(task)
        raise


async def _fetch_in_python(route: Route) -> None:
    """Fulfill a resolver page request from Python, so sources need no CORS."""
    try:
        # Without micropip's Accept, indexes answer with HTML. micropip 0.11
        # leaves relative file URLs in JSON index pages unresolved.
        response = await asyncio.to_thread(
            requests.get, route.request.url, timeout=60
        )
    except Exception:
        # An unsettled route stalls the page until the resolver timeout.
        await route.abort()
        return
    headers = {key.lower(): value for key, value in response.headers.items()}
    await route.fulfill(
        status=response.status_code,
        body=response.content,
        headers={
            "access-control-allow-origin": "*",
            # micropip picks the index page parser by content type.
            "content-type": headers.get(
                "content-type", "application/octet-stream"
            ),
        },
    )


def _rewrite_requirements(code: str, packages: dict[str, _Package]) -> str:
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.utils import canonicalize_name

    project = script_metadata.loads(code)
    if project is None:
        return code
    dependencies = []
    for value in project.get("dependencies", []):
        requirement = Requirement(str(value))
        name = canonicalize_name(requirement.name)
        requirement.name = name
        if name == "marimo":
            # The exported runtime skips requirements named after loaded
            # modules. With extras, it would ask micropip for marimo.
            requirement.extras = set()
        if requirement.url and name in packages:
            requirement.url = None
            requirement.specifier = SpecifierSet(
                f"=={packages[name]['version']}"
            )
        dependencies.append(str(requirement))
    project["dependencies"] = dependencies
    return script_metadata.replace_block(code, script_metadata.dumps(project))


async def check_offline_export_browser() -> None:
    """Verify the resolver's browser can start before downloading assets."""
    from playwright.async_api import async_playwright  # type: ignore[import-not-found]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        await browser.close()


async def _resolve_packages(
    code: str,
    *,
    page_url: str,
    index_url: str,
    package_base_url: str,
    lockfile: _Lockfile,
    pypi_index_url: str | None,
) -> _Lockfile:
    from playwright.async_api import async_playwright  # type: ignore[import-not-found]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            origin = urljoin(page_url, "/")
            await page.route(
                lambda url: not url.startswith(origin), _fetch_in_python
            )
            await page.goto(page_url)
            resolution = await asyncio.wait_for(
                page.evaluate(
                    _RESOLVE_PACKAGES,
                    {
                        "indexURL": index_url,
                        "packageBaseUrl": package_base_url,
                        "lockfile": lockfile,
                        "pypiIndexUrl": pypi_index_url,
                        "pyodideVersion": PYODIDE_VERSION,
                        "marimoVersion": __version__,
                        "code": code,
                        "requirements": PyProjectReader.from_script(
                            code
                        ).dependencies,
                    },
                ),
                timeout=300,
            )
        finally:
            await browser.close()
    return _lock_required(resolution)


def _publish_bundle(
    staging: Path,
    output_dir: Path,
    resolved: _Lockfile,
    hashes: dict[Path, str],
    pyodide_lockfile: _Lockfile,
) -> str:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    pyodide_packages = {
        canonicalize_name(name) for name in pyodide_lockfile["packages"]
    }
    for name, package in resolved["packages"].items():
        name = canonicalize_name(Requirement(name).name)
        filename = package["file_name"]
        source = staging / "downloads" / filename
        digest = hashes[source]
        relative = f"{digest}/{filename}"
        target = staging / "packages" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            source.replace(target)
        package["sha256"] = digest
        package["file_name"] = f"../packages/{relative}"
        if name in pyodide_packages:
            # The exported runtime prefers index pages over the lockfile, and
            # Pyodide-built wheels can require packages their entries omit,
            # such as tzdata for pandas.
            continue
        index = staging / "packages" / "index" / name / "index.html"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            f'<!doctype html><a href="../../{quote(relative)}">{html.escape(filename)}</a>',
            encoding="utf-8",
        )
    # Existing exports keep the exact dependency set they were built with.
    lock_contents = json.dumps(resolved, sort_keys=True)
    lock_name = (
        hashlib.sha256(lock_contents.encode()).hexdigest()[:16] + ".json"
    )
    (staging / "lockfile").mkdir()
    (staging / "lockfile" / lock_name).write_text(
        lock_contents, encoding="utf-8"
    )
    # Publish the lockfile after its files, replacing individual files atomically.
    for directory in ("pyodide", "packages", "lockfile"):
        for source in (staging / directory).rglob("*"):
            if source.is_file():
                target = output_dir / source.relative_to(staging)
                target.parent.mkdir(parents=True, exist_ok=True)
                source.replace(target)
    return lock_name


async def bundle_wasm_runtime(
    code: str,
    output_dir: Path,
    *,
    sources: WASMRuntimeConfig,
    local_wheel_paths: tuple[Path, ...] = (),
) -> tuple[str, WASMRuntimeConfig]:
    """Resolve packages in Pyodide and vendor them without executing cells."""
    if sources.pyodide_index_url:
        index_url = sources.pyodide_index_url.rstrip("/") + "/"
        # marimo's hosted lockfile only describes the default distribution.
        default_lockfile_url = index_url + "pyodide-lock.json"
    else:
        index_url = (
            f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
        )
        default_lockfile_url = (
            f"https://wasm.marimo.app/pyodide-lock.json?v={__version__}"
            f"&pyodide=v{PYODIDE_VERSION}"
        )
    lockfile_url = sources.pyodide_lockfile_url or default_lockfile_url
    try:
        lockfile = json.loads(await asyncio.to_thread(_fetch, lockfile_url))
    except json.JSONDecodeError as error:
        raise OfflineExportError(
            f"{lockfile_url} is not a Pyodide lockfile: {error}"
        ) from error
    pypi_index_url = sources.pypi_index_url
    if pypi_index_url and "{package_name}" not in pypi_index_url:
        # micropip appends "/<name>/", so pip-style trailing slashes would double.
        pypi_index_url = pypi_index_url.rstrip("/")
    await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".marimo-offline-", dir=output_dir
    ) as tmp:
        staging = Path(tmp)
        for wheel in local_wheel_paths:
            target = staging / "public" / "wheels" / wheel.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wheel, target)
        await _download_all(
            {
                staging / "pyodide" / name: (urljoin(index_url, name), None)
                for name in (
                    "pyodide.mjs",
                    "pyodide.asm.mjs",
                    "pyodide.asm.wasm",
                    "python_stdlib.zip",
                )
            }
        )
        # Match the browser workers' base so existing ../public/wheels URLs resolve.
        with HtmlAssetServer(
            directory=staging, route="/assets/offline.html"
        ) as server:
            server.set_html(
                "<!doctype html><title>Resolve notebook packages</title>"
            )
            resolved = await _resolve_packages(
                code,
                page_url=server.page_url,
                index_url=f"{server.base_url}/pyodide/",
                package_base_url=index_url,
                lockfile=lockfile,
                pypi_index_url=pypi_index_url,
            )
            downloads: dict[Path, tuple[str, str | None]] = {}
            for package in resolved["packages"].values():
                url = urljoin(index_url, package["file_name"])
                filename = unquote(urlparse(url).path.rsplit("/", 1)[-1])
                if not filename or Path(filename).name != filename:
                    raise ValueError(f"Invalid package filename: {url}")
                target = staging / "downloads" / filename
                source = (url, package["sha256"])
                if target in downloads and downloads[target] != source:
                    raise ValueError(
                        f"Conflicting package filename: {filename}"
                    )
                downloads[target] = source
                package["file_name"] = filename
            hashes = await _download_all(downloads)
        lock_name = _publish_bundle(
            staging, output_dir, resolved, hashes, lockfile
        )
    return _rewrite_requirements(
        code, resolved["packages"]
    ), WASMRuntimeConfig(
        pyodide_index_url="./pyodide/",
        pyodide_lockfile_url=f"./lockfile/{lock_name}",
        pypi_index_url="./packages/index/",
    )
