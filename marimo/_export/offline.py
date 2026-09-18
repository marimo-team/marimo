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
from typing import TypedDict
from urllib.parse import quote, unquote, urljoin, urlparse

from marimo._environments import script_metadata
from marimo._export._html_asset_server import HtmlAssetServer
from marimo._pyodide.pyodide_constraints import PYODIDE_VERSION
from marimo._schemas.export_options import WASMRuntimeConfig
from marimo._utils import requests
from marimo._utils.inline_script_metadata import PyProjectReader
from marimo._version import __version__


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


_RESOLVE_PACKAGES = r"""async ({ indexURL, packageBaseUrl, lockfile, pypiIndexUrl, code, requirements }) => {
    const { loadPyodide } = await import(indexURL + "pyodide.mjs");
    const pyodide = await loadPyodide({ indexURL, packageBaseUrl, lockFileContents: lockfile });
    const errors = [];
    const callbacks = { errorCallback: message => errors.push(message) };
    await pyodide.loadPackage(
        ["micropip", "marimo-base", "docutils", "pygments", "jedi", "pyodide-http", "black"],
        callbacks,
    );
    if (errors.length) throw new Error(errors.join("\n"));
    pyodide.globals.set("requirements_json", JSON.stringify(requirements));
    pyodide.globals.set("index_url", pypiIndexUrl);
    pyodide.globals.set("base_url", location.href);
    await pyodide.runPythonAsync(`
import json
import micropip
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from urllib.parse import urljoin

if index_url:
    micropip.set_index_urls(index_url)
requirements = []
requirement_names = []
for value in json.loads(requirements_json):
    requirement = Requirement(value)
    if requirement.marker and not requirement.marker.evaluate():
        continue
    if canonicalize_name(requirement.name) == "marimo":
        requirement.name = "marimo-base"
    if requirement.url:
        requirement.url = urljoin(base_url, requirement.url)
    requirements.append(str(requirement))
    requirement_names.append(canonicalize_name(requirement.name))
await micropip.install(requirements)
`);
    // Keep the same SQL dependency policy as shouldLoadDuckDBPackages.
    const usesDuckDB = /(^|\n)\s*(?:import\s+[^\n#]*\bduckdb\b|from\s+duckdb\b|[^\n#]*\bduckdb\s*\.)/.test(code);
    if (code.includes("mo.sql") || usesDuckDB || pyodide.runPython('"duckdb" in requirement_names')) {
        code += "\nimport duckdb, pandas, sqlglot";
        if (code.includes("polars")) code += "\nimport pyarrow";
    }
    await pyodide.loadPackagesFromImports(code, callbacks);
    if (errors.length) throw new Error(errors.join("\n"));
    const frozen = JSON.parse(pyodide.runPython("micropip.freeze()"));
    const loaded = new Set([...Object.keys(pyodide.loadedPackages), "marimo-base"].map(name => name.toLowerCase().replace(/[-_.]+/g, "-")));
    frozen.packages = Object.fromEntries(Object.entries(frozen.packages).filter(([name]) => loaded.has(name)));
    return frozen;
}"""


def _download(url: str, target: Path, sha256: str | None = None) -> str:
    data = requests.get(url, timeout=60).raise_for_status().content
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
            await page.goto(page_url)
            return await asyncio.wait_for(
                page.evaluate(
                    _RESOLVE_PACKAGES,
                    {
                        "indexURL": index_url,
                        "packageBaseUrl": package_base_url,
                        "lockfile": lockfile,
                        "pypiIndexUrl": pypi_index_url,
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


def _publish_bundle(
    staging: Path,
    output_dir: Path,
    resolved: _Lockfile,
    hashes: dict[Path, str],
) -> str:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

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
    index_url = sources.pyodide_index_url or (
        f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
    )
    index_url = index_url.rstrip("/") + "/"
    lockfile_url = sources.pyodide_lockfile_url or (
        f"https://wasm.marimo.app/pyodide-lock.json?v={__version__}"
        f"&pyodide=v{PYODIDE_VERSION}"
    )
    lockfile = await asyncio.to_thread(
        lambda: (
            requests.get(lockfile_url, timeout=60).raise_for_status().json()
        )
    )
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
                pypi_index_url=sources.pypi_index_url,
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
        lock_name = _publish_bundle(staging, output_dir, resolved, hashes)
    return _rewrite_requirements(
        code, resolved["packages"]
    ), WASMRuntimeConfig(
        pyodide_index_url="./pyodide/",
        pyodide_lockfile_url=f"./lockfile/{lock_name}",
        pypi_index_url="./packages/index/",
    )
