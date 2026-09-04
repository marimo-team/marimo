# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import msgspec
import pytest

from marimo._runtime.commands import ExecuteCellCommand
from marimo._save import signing
from marimo._save.loaders import lazy
from marimo._save.stubs.lazy_stub import Cache as CacheSchema
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from pathlib import Path


def _read_manifest(path: Path) -> CacheSchema:
    manifests = list(path.rglob("*.jsonl"))
    assert len(manifests) == 1
    return msgspec.json.decode(manifests[0].read_bytes(), type=CacheSchema)


@pytest.mark.requires("cryptography")
@pytest.mark.parametrize("form", ["function", "async", "context"])
async def test_persistent_cache_defaults_to_signed_lazy(
    form: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signer = signing.CacheSigner.from_private_key_pem(
        signing.generate_keypair()[0]
    )
    monkeypatch.setattr(
        lazy, "_get_default_signer", lambda *_args, **_kwargs: signer
    )
    monkeypatch.setattr(
        lazy, "_get_machine_signer", lambda *_args, **_kwargs: signer
    )
    arguments = f"save_path={str(tmp_path)!r}"
    if form == "context":
        code = f'with mo.persistent_cache("default", {arguments}):\n    result = 42'
    else:
        prefix = "async " if form == "async" else ""
        await_call = "await " if form == "async" else ""
        code = (
            f"@mo.persistent_cache({arguments})\n"
            f"{prefix}def compute():\n    return 42\n"
            f"result = {await_call}compute()"
        )
    with mocked_kernel_session() as tk:
        await tk.kernel.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("imports"), code="import marimo as mo"
                ),
                ExecuteCellCommand(cell_id=CellId_t("cache"), code=code),
            ]
        )
        assert tk.kernel.globals["result"] == 42
        lazy.LazyLoader.flush_all()
        schema = await asyncio.to_thread(_read_manifest, tmp_path)
        assert schema.meta.signature is not None
        signer.verify(lazy._signable_bytes(schema), schema.meta.signature)


@pytest.mark.requires("cryptography")
def test_concurrent_key_creation_keeps_one_identity(tmp_path: Path) -> None:
    key_path = tmp_path / "key.pem"
    both_generating = threading.Barrier(2)
    first_returned = threading.Event()
    original_generate = signing.generate_keypair
    original_replace, original_link = os.replace, os.link
    signers: dict[str, signing.CacheSigner | None] = {}
    failures: list[Exception] = []

    def generate() -> tuple[str, str]:
        pair = original_generate()
        both_generating.wait(timeout=10)
        return pair

    def publish(operation: Any, *args: Any, **kwargs: Any) -> None:
        # Both callers observed a missing key, but the first finishes before
        # the second publishes its candidate.
        if threading.current_thread().name == "second":
            assert first_returned.wait(timeout=10)
        operation(*args, **kwargs)

    def resolve() -> None:
        name = threading.current_thread().name
        try:
            signers[name] = signing._get_machine_signer(str(key_path))
        except Exception as exc:
            failures.append(exc)
        finally:
            if name == "first":
                first_returned.set()

    with (
        patch.object(signing, "generate_keypair", generate),
        patch.object(
            os, "replace", lambda *a, **kw: publish(original_replace, *a, **kw)
        ),
        patch.object(
            os, "link", lambda *a, **kw: publish(original_link, *a, **kw)
        ),
    ):
        threads = [
            threading.Thread(target=resolve, name=name)
            for name in ("first", "second")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
    assert not failures
    persisted = signing.CacheSigner.from_private_key_pem(key_path.read_text())
    for signer in signers.values():
        assert signer is not None
        persisted.verify(b"cached result", signer.sign(b"cached result"))


@pytest.mark.requires("cryptography")
def test_persistent_default_verifies_across_restarts(tmp_path: Path) -> None:
    private_pem, _ = signing.generate_keypair()
    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        "import marimo\napp = marimo.App()\n"
        "with app.setup:\n    import marimo as mo\n"
        "@app.cell\ndef _():\n"
        f"    with mo.persistent_cache('restart', save_path={str(tmp_path / 'cache')!r}) as cache:\n"
        "        print('computed')\n        value = 42\n"
        "    print(f'value={value};hit={cache.hit}')\n    return\n"
        "if __name__ == '__main__':\n    app.run()\n"
    )
    env = dict(os.environ, MARIMO_CACHE_SIGNING_PRIVATE_KEY=private_pem)

    def run() -> str:
        return subprocess.run(
            [sys.executable, str(notebook)],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout

    assert run().splitlines() == ["computed", "value=42;hit=False"]
    assert run().splitlines() == ["value=42;hit=True"]
    manifest = next((tmp_path / "cache").rglob("*.jsonl"))
    data = msgspec.json.decode(manifest.read_bytes())
    data["meta"]["signature"] = "A" * 88
    manifest.write_bytes(msgspec.json.encode(data))
    assert run().splitlines() == ["computed", "value=42;hit=False"]
