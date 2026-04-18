# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from unittest import mock

import pytest

from marimo._runtime.parent_poller import ParentPollerUnix


@pytest.mark.skipif(os.name == "nt", reason="only works on posix")
def test_parent_poller_unix_reparent_to_pid1():
    poller = ParentPollerUnix(parent_pid=221)

    with (
        mock.patch("os.getppid", return_value=1),
        mock.patch("os.killpg"),
        mock.patch("os._exit", side_effect=SystemExit(1)),
        pytest.raises(SystemExit),
    ):
        poller.run()


@pytest.mark.skipif(os.name == "nt", reason="only works on posix")
def test_parent_poller_unix_reparent_not_pid1():
    parent_pid = 221
    poller = ParentPollerUnix(parent_pid=parent_pid)

    with (
        mock.patch("os.getppid", side_effect=[parent_pid, parent_pid - 1]),
        mock.patch("os.killpg"),
        mock.patch("os._exit", side_effect=SystemExit(1)),
        pytest.raises(SystemExit),
    ):
        poller.run()


@pytest.mark.skipif(os.name == "nt", reason="only works on posix")
def test_parent_poller_unix_propagates_getppid_error():
    poller = ParentPollerUnix(parent_pid=221)

    with (
        mock.patch("os.getppid", side_effect=ValueError("boom")),
        pytest.raises(ValueError, match="boom"),
    ):
        poller.run()
