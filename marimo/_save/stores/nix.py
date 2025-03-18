# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import dataclasses
from hashlib import md5
from typing import TYPE_CHECKING

# import boto3
import requests
import zstandard as zstd

from marimo._save.stores.store import Store

if TYPE_CHECKING:
    from marimo._save.cache import Cache
    from marimo._save.hash import HashKey
    from marimo._save.loaders import BasePersistenceLoader as Loader


def compress_blob(blob: bytes, level: int = 3) -> bytes:
    compressor = zstd.ZstdCompressor(level=level)
    return compressor.compress(blob)


def decompress_blob(blob: bytes) -> bytes:
    decompressor = zstd.ZstdDecompressor()
    return decompressor.decompress(blob)


# TODO: Fix, abstract from just Cachix
class NixRemoteStore(Store):
    """
    A remote Nix store implementation that interacts with Cachix.org.

    This implementation mimics the API of FileStore but uses HTTP requests
    to put and get serialized NAR files to/from a Cachix binary cache.
    """

    def __init__(
        self,
        cache_name: str = "marimo",
        auth_token: str = "",
        base_url: str = "https://app.cachix.org/api/v1",
    ):
        """
        Initializes the remote store with Cachix credentials.

        Args:
            cache_name (str): The name of the Cachix cache.
            auth_token (str): The API token for authentication.
            base_url (str): The base URL for the Cachix service.
        """
        self.cache_name = cache_name
        self.auth_token = auth_token
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.auth_token}",
                # "Content-Type": "application/octet-stream",
            }
        )

    def get(self, key: HashKey, _: Loader) -> bytes:
        """
        Retrieves a NAR file from the remote Cachix cache.

        Args:
            key (HashKey): The hash key identifying the NAR.
            loader (Loader): Loader instance (may be used for additional processing).

        Returns:
            bytes: The binary contents of the NAR file.

        Raises:
            requests.HTTPError: If the GET request fails.
        """
        url = f"https://{self.cache_name}.cachix.org/{key.hash}.nar"
        response = self.session.get(url)
        response.raise_for_status()
        compressed_blob = response.content
        blob = decompress_blob(compressed_blob)
        return deserialise(blob).contents

    def put(self, cache: Cache, loader: Loader) -> None:
        """
        Serializes a cache object to a NAR blob via the loader and uploads it.

        Args:
            cache (Cache): The cache object containing data to be stored.
            loader (Loader): Loader instance providing the `to_blob` method.

        Raises:
            requests.HTTPError: If the PUT request fails.
        """
        blob = loader.to_blob(cache)
        if blob is None:
            return
        nar_blob = serialise(FSObject(type="Regular", contents=blob))
        if nar_blob is None:
            return

        # TODO: Something's not working. Maybe just use boto3

        # Step 1: Initiate multipart upload
        init_url = f"{self.base_url}/cache/{self.cache_name}/multipart-nar"
        init_response = self.session.post(init_url)
        init_response.raise_for_status()
        init_data = init_response.json()
        nar_uuid, upload_id = init_data["narId"], init_data["uploadId"]

        # Step 2: Upload parts
        part_size = 8 * 1024 * 1024  # 8MB
        parts = []
        for i, offset in enumerate(
            range(0, len(nar_blob), part_size), start=1
        ):
            part_blob = nar_blob[offset : offset + part_size]
            sign_url = f"{self.base_url}/cache/{self.cache_name}/multipart-nar/{nar_uuid}?uploadId={upload_id}&partNumber={i}"
            md5_hash = md5(part_blob).digest()
            content_md5 = base64.b64encode(md5_hash).decode("utf-8")
            sign_response = self.session.post(
                sign_url, json={"contentMD5": content_md5}
            )

            sign_response.raise_for_status()
            upload_url = sign_response.json()["uploadUrl"]

            # ...? Fails with 400
            upload_response = self.session.put(
                upload_url,
                data=part_blob,
                headers={
                    "Content-MD5": content_md5,
                    "Content-Type": "application/octet-stream",
                },
            )
            upload_response.raise_for_status()
            parts.append(
                {"partNumber": i, "etag": upload_response.headers["ETag"]}
            )

        # Step 3: Complete upload
        complete_url = f"{self.base_url}/cache/{self.cache_name}/multipart-nar/{nar_uuid}/complete?uploadId={upload_id}"
        complete_response = self.session.post(
            complete_url, json={"parts": parts}
        )
        complete_response.raise_for_status()

    def hit(self, key: HashKey, _loader: Loader) -> bool:
        """
        Checks whether the NAR corresponding to the key exists in the remote store.

        Args:
            key (HashKey): The hash key of the NAR.
            loader (Loader): Loader instance (unused here).

        Returns:
            bool: True if the object exists; otherwise, False.
        """
        url = f"https://{self.cache_name}.cachix.org/{key.hash}.narinfo"
        response = self.session.head(url)
        return response.status_code == 200


# This is taken directly from Figure 5.2 in http://nixos.org/~eelco/pubs/phd-thesis.pdf.
# gist: https://gist.github.com/jbeda/5c79d2b1434f0018d693


@dataclasses.dataclass
class FSObject:
    type: str
    exec: str = "NonExecutable"
    contents: bytes = b""
    target: bytes = b""
    entries: dict[bytes, FSObject] = dataclasses.field(default_factory=dict)


def sortEntries(entries: dict[bytes, FSObject]) -> list[bytes]:
    return sorted(entries.keys())


def _int(n: int) -> bytes:
    return n.to_bytes(8, "little")


def pad(s: bytes) -> bytes:
    return s + b"\0" * (-len(s) % 8)


def _str(s: bytes) -> bytes:
    return _int(len(s)) + pad(s)


def serialise(fso: FSObject) -> bytes:
    return b"nix-archive-1" + serialise1(fso)


def serialise1(fso: FSObject) -> bytes:
    return b"(" + serialise2(fso) + b")"


def serialise2(fso: FSObject) -> bytes:
    if fso.type == "Regular":
        result = _str(b"type") + _str(b"regular")
        if fso.exec == "Executable":
            result += _str(b"executable") + _str(b"")
        result += _str(b"contents") + _str(fso.contents)
        return result
    elif fso.type == "SymLink":
        return (
            _str(b"type")
            + _str(b"symlink")
            + _str(b"target")
            + _str(fso.target)
        )
    elif fso.type == "Directory":
        result = _str(b"type") + _str(b"directory")
        for name, entry in sorted(fso.entries.items()):
            result += serialise_entry(name, entry)
        return result
    else:
        raise ValueError(f"Unsupported FSObject type: {fso.type}")


def serialise_entry(name: bytes, fso: FSObject) -> bytes:
    return (
        _str(b"entry")
        + _str(b"(")
        + _str(b"name")
        + _str(name)
        + _str(b"node")
        + serialise1(fso)
        + _str(b")")
    )


# Helpers for reading from the blob


def read_int(blob: bytes, offset: int) -> tuple[int, int]:
    """Read an 8-byte little-endian integer from blob starting at offset."""
    value = int.from_bytes(blob[offset : offset + 8], "little")
    return value, offset + 8


def read_str(blob: bytes, offset: int) -> tuple[bytes, int]:
    """
    Reads a length-prefixed, padded string.
    The string is encoded as:
        int(|s|) + s + pad(s)
    where pad(s) is zero bytes to pad the length to a multiple of 8.
    """
    length, offset = read_int(blob, offset)
    s = blob[offset : offset + length]
    # Calculate padding: pad_len = (-length) mod 8.
    pad_len = (-length) % 8
    offset += length + pad_len
    return s, offset


# a minimal recursive parse for NAR deserialisation


def deserialise(blob: bytes) -> FSObject:
    """
    Convert a NAR blob (bytes) back into an FSObject.
    Expects the blob to begin with b"nix-archive-1" followed by a serialized expression.
    """
    prefix = b"nix-archive-1"
    if not blob.startswith(prefix):
        raise ValueError("Invalid NAR blob: missing 'nix-archive-1' prefix")
    offset = len(prefix)
    fso, offset = parse_expr(blob, offset)
    return fso


def parse_expr(blob: bytes, offset: int) -> tuple[FSObject, int]:
    """
    Parses a NAR expression. A serialized FSObject is wrapped between tokens "(" and ")".
    """
    # Expect an opening parenthesis.
    token, offset = read_str(blob, offset)
    if token != b"(":
        raise ValueError("Expected '(' at beginning of NAR expression")
    # Parse tokens until we reach a closing parenthesis.
    tokens = []
    while True:
        token, offset = read_str(blob, offset)
        if token == b")":
            break
        tokens.append(token)
    # Interpret the flat list of tokens.
    return interpret_tokens(tokens), offset


def interpret_tokens(tokens: list[bytes]) -> FSObject:
    """
    Given a flat list of tokens from a NAR expression,
    interpret them to construct an FSObject.

    For a Regular file, expects:
      ["type", "regular", ("executable", "")?, "contents", <contents>]
    For a Symlink, expects:
      ["type", "symlink", "target", <target>]
    """
    if not tokens or tokens[0] != b"type":
        raise ValueError("Expected 'type' token in NAR expression")
    if tokens[1] == b"regular":
        fso = FSObject(type="Regular")
        idx = 2
        # Optional "executable" token.
        if idx < len(tokens) and tokens[idx] == b"executable":
            fso.exec = "Executable"
            idx += 2  # Skip the next (empty) token.
        else:
            fso.exec = "NonExecutable"
        if idx >= len(tokens) or tokens[idx] != b"contents":
            raise ValueError("Expected 'contents' token in Regular file")
        idx += 1
        if idx >= len(tokens):
            raise ValueError("Missing contents value for Regular file")
        fso.contents = tokens[idx]
        return fso
    elif tokens[1] == b"symlink":
        if len(tokens) < 4 or tokens[2] != b"target":
            raise ValueError("Malformed symlink tokens in NAR blob")
        return FSObject(type="SymLink", target=tokens[3])
    elif tokens[1] == b"directory":
        # For directories, you'd expect a series of entries.
        # Here, we provide a stub implementation.
        return FSObject(type="Directory")
    else:
        raise ValueError(
            f"Unsupported FSObject type in NAR: {tokens[1].decode()}"
        )
