# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from os import path

from tests._server.templates.utils import normalize_index_html
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_cli_export_html(temp_marimo_file: str) -> None:
    p = subprocess.run(
        ["marimo", "export", "html", temp_marimo_file],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    html = normalize_index_html(p.stdout.decode())
    # Remove folder path
    dirname = path.dirname(temp_marimo_file)
    html = html.replace(dirname, "path")
    snapshot("test_cli_export_html.txt", html)


def test_cli_export_html_no_code(temp_marimo_file: str) -> None:
    p = subprocess.run(
        ["marimo", "export", "html", temp_marimo_file, "--no-include-code"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    html = normalize_index_html(p.stdout.decode())
    # Remove folder path
    dirname = path.dirname(temp_marimo_file)
    html = html.replace(dirname, "path")
    snapshot("test_cli_export_html_no_code.txt", html)


async def test_export_watch(temp_marimo_file: str) -> None:
    temp_out_file = temp_marimo_file.replace(".py", ".html")
    p = subprocess.Popen(  # noqa: ASYNC101
        [
            "marimo",
            "export",
            "html",
            temp_marimo_file,
            "--watch",
            "--output",
            temp_out_file,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the message
    while True:
        line = p.stdout.readline().decode()
        if line:
            assert f"Watching {temp_marimo_file}" in line
            break

    assert not path.exists(temp_out_file)

    # Modify file
    with open(temp_marimo_file, "a") as f:  # noqa: ASYNC101
        f.write("\n# comment\n")
        f.close()

    # Wait for rebuild
    while True:
        line = p.stdout.readline().decode()
        if line:
            assert "Re-exporting" in line
            break


def test_export_watch_no_out_dir(temp_marimo_file: str) -> None:
    p = subprocess.Popen(
        [
            "marimo",
            "export",
            "html",
            temp_marimo_file,
            "--watch",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Should return an error
    while True:
        line = p.stderr.readline().decode()
        if line:
            assert (
                "Cannot use --watch without providing "
                + "an output file with --output."
                in line
            )
            break
