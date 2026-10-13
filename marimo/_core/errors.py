# Copyright 2026 Marimo. All rights reserved.
"""Exceptions raised by host and notebook commands."""

from __future__ import annotations


class HostError(Exception):
    """Base exception for host and notebook commands."""


class NotFound(HostError):
    """The requested object does not exist."""


class Conflict(HostError):
    """The command cannot run in the current state."""


class NoRuntime(Conflict):
    """The command requires a runtime, but the notebook has none."""
