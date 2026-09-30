# Copyright 2026 Marimo. All rights reserved.
"""Identity and local selection for an active Pair connection."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

import msgspec

from marimo._cli.pair.client import PairInputError
from marimo._messaging.participants import HarnessMetadata
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

IdentityScope = Literal["conversation", "harness"]
_OVERRIDE_HARNESS_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


@dataclass(frozen=True)
class PairIdentity:
    harness: HarnessMetadata
    scope: IdentityScope
    conversation_id: str | None = field(default=None, repr=False)


class PairConnection(msgspec.Struct, frozen=True, rename="camel"):
    version: Literal[1]
    stable_session_id: str
    participant_id: str
    harness: HarnessMetadata
    scope: IdentityScope
    connected_at: str
    last_used_at: str


@dataclass(frozen=True)
class SelectedConnection:
    connection: PairConnection
    path: Path


def resolve_identity(
    environ: Mapping[str, str],
    *,
    harness_id: str | None = None,
    harness_name: str | None = None,
) -> PairIdentity:
    """Resolve explicit overrides or use the shared harness fallback."""
    override_harness = environ.get("MARIMO_PAIR_HARNESS", "")
    conversation_id = environ.get("MARIMO_PAIR_CONVERSATION_ID", "")
    if bool(override_harness) != bool(conversation_id.strip()):
        raise PairInputError(
            "Set both MARIMO_PAIR_HARNESS and "
            "MARIMO_PAIR_CONVERSATION_ID, or neither."
        )
    if conversation_id and not conversation_id.strip():
        raise PairInputError("MARIMO_PAIR_CONVERSATION_ID must not be empty.")
    if harness_id is not None and not harness_id.strip():
        raise PairInputError("--harness-id must not be empty.")
    if harness_name is not None and not harness_name.strip():
        raise PairInputError("--harness-name must not be empty.")
    if override_harness:
        if _OVERRIDE_HARNESS_PATTERN.fullmatch(override_harness) is None:
            raise PairInputError(
                "MARIMO_PAIR_HARNESS must use lowercase letters, digits, "
                "or hyphens."
            )
        if harness_id is not None and harness_id != override_harness:
            raise PairInputError(
                "--harness-id must match MARIMO_PAIR_HARNESS."
            )
    if (
        harness_name is not None
        and harness_id is None
        and not override_harness
    ):
        raise PairInputError(
            "--harness-name requires --harness-id or MARIMO_PAIR_HARNESS."
        )

    resolved_id = override_harness or harness_id or "unknown"
    resolved_name = harness_name or "Agent"
    try:
        harness = HarnessMetadata(id=resolved_id, display_name=resolved_name)
    except ValueError as error:
        raise PairInputError(str(error)) from error
    return PairIdentity(
        harness=harness,
        scope="conversation" if conversation_id else "harness",
        conversation_id=conversation_id or None,
    )


def participant_id(stable_session_id: str, identity: PairIdentity) -> str:
    """Derive the versioned server identity independently of the URL."""
    values = [
        "marimo-participant-v1",
        stable_session_id,
        identity.harness.id,
        identity.scope,
        identity.conversation_id,
    ]
    encoded = json.dumps(
        values, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    return "p1_" + hashlib.sha256(encoded).hexdigest()


def _server_target(url: str) -> str:
    """Keep the origin and base path, excluding URL credentials and queries."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise PairInputError("The server URL is invalid.") from error
    if parsed.scheme not in ("http", "https") or parsed.hostname is None:
        raise PairInputError("The server URL must use http or https.")
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    origin = f"{parsed.scheme.lower()}://{host}"
    if port is not None:
        origin += f":{port}"
    return origin + parsed.path.rstrip("/")


def _lookup_digest(
    url: str, stable_session_id: str, identity: PairIdentity
) -> str:
    values = [
        "marimo-pair-connection-v1",
        _server_target(url),
        stable_session_id,
        identity.harness.id,
        identity.scope,
        identity.conversation_id,
    ]
    encoded = json.dumps(
        values, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ConnectionStore:
    """Store one small file per Pair binding under the platform state dir."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (
            root
            if root is not None
            else marimo_state_dir() / "pair" / "connections-v1"
        )

    def _path(
        self, url: str, stable_session_id: str, identity: PairIdentity
    ) -> Path:
        return (
            self.root
            / f"{_lookup_digest(url, stable_session_id, identity)}.json"
        )

    def save(
        self,
        *,
        url: str,
        stable_session_id: str,
        identity: PairIdentity,
        participant: str,
    ) -> SelectedConnection:
        path = self._path(url, stable_session_id, identity)
        try:
            previous = self._read(path)
        except PairInputError:
            previous = None
        now = _now()
        connection = PairConnection(
            version=1,
            stable_session_id=stable_session_id,
            participant_id=participant,
            harness=identity.harness,
            scope=identity.scope,
            connected_at=previous.connected_at if previous else now,
            last_used_at=now,
        )
        self._write(path, connection)
        return SelectedConnection(connection=connection, path=path)

    def load(
        self, *, url: str, stable_session_id: str, identity: PairIdentity
    ) -> SelectedConnection | None:
        direct_path = self._path(url, stable_session_id, identity)
        direct = self._read(direct_path)
        if direct is not None and not self._matches(
            direct, stable_session_id, identity
        ):
            raise PairInputError(
                "The Pair connection file has a mismatched identity."
            )
        if identity.scope == "conversation":
            if direct is None:
                return None
            return SelectedConnection(direct, direct_path)

        # A generic caller can omit the advisory harness ID on later calls.
        # Select only when one fallback binding targets this server and Session.
        candidates: list[SelectedConnection] = []
        if direct is not None:
            candidates.append(SelectedConnection(direct, direct_path))
        try:
            paths = self.root.glob("*.json")
            for path in paths:
                if path == direct_path:
                    continue
                try:
                    connection = self._read(path)
                except PairInputError:
                    continue
                if connection is None or connection.scope != "harness":
                    continue
                candidate_identity = PairIdentity(
                    harness=connection.harness, scope="harness"
                )
                expected = self._path(
                    url, stable_session_id, candidate_identity
                )
                if path == expected:
                    if not self._matches(
                        connection, stable_session_id, candidate_identity
                    ):
                        raise PairInputError(
                            "The Pair connection file has a mismatched identity."
                        )
                    candidates.append(SelectedConnection(connection, path))
        except OSError as error:
            raise PairInputError(
                "Could not read the Pair connection directory."
            ) from error
        if len(candidates) > 1:
            raise PairInputError(
                "Several Pair connections match this session. "
                "Run marimo pair connect again with a conversation identity."
            )
        return candidates[0] if candidates else None

    @staticmethod
    def _matches(
        connection: PairConnection,
        stable_session_id: str,
        identity: PairIdentity,
    ) -> bool:
        return (
            connection.stable_session_id == stable_session_id
            and connection.harness.id == identity.harness.id
            and connection.scope == identity.scope
            and connection.participant_id
            == participant_id(stable_session_id, identity)
        )

    def touch(self, selected: SelectedConnection) -> SelectedConnection:
        previous = selected.connection
        updated = PairConnection(
            version=1,
            stable_session_id=previous.stable_session_id,
            participant_id=previous.participant_id,
            harness=previous.harness,
            scope=previous.scope,
            connected_at=previous.connected_at,
            last_used_at=_now(),
        )
        self._write(selected.path, updated)
        return SelectedConnection(updated, selected.path)

    def remove(self, selected: SelectedConnection) -> None:
        try:
            selected.path.unlink(missing_ok=True)
        except OSError as error:
            raise PairInputError(
                "Could not remove the Pair connection file."
            ) from error

    def _read(self, path: Path) -> PairConnection | None:
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise PairInputError(
                "Could not read the Pair connection file."
            ) from error
        try:
            return msgspec.json.decode(raw, type=PairConnection)
        except (msgspec.MsgspecError, ValueError) as error:
            raise PairInputError(
                "The Pair connection file is invalid. Run marimo pair connect again."
            ) from error

    def _write(self, path: Path, connection: PairConnection) -> None:
        try:
            self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
            if os.name == "posix":
                os.chmod(self.root, 0o700)
            descriptor, temporary = tempfile.mkstemp(
                dir=self.root, suffix=".tmp"
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    if os.name == "posix":
                        os.fchmod(stream.fileno(), 0o600)
                    stream.write(msgspec.json.encode(connection))
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        except OSError as error:
            raise PairInputError(
                "Could not save the Pair connection. Run marimo pair connect again."
            ) from error
