# Copyright 2026 Marimo. All rights reserved.
"""Local address and bearer validation shared by agent endpoints."""

from __future__ import annotations

import hmac
import re
from ipaddress import IPv6Address, ip_address

_PORT = re.compile(r"[0-9]{1,5}")


def is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_loopback


def host_header_ok(header: str | None, port: int) -> bool:
    """Check that the Host header names a loopback address and server port."""
    if header is None:
        return False
    if header.startswith("["):
        name, closed, after = header.partition("]")
        if not closed or (after and not after.startswith(":")):
            return False
        name = name[1:]
        given = after[1:]
    else:
        name, _, given = header.partition(":")
    if not is_loopback(name):
        return False
    if given == "":
        return port == 80
    return _PORT.fullmatch(given) is not None and int(given) == port


def bearer_matches(authorization: str | None, token: str) -> bool:
    if authorization is None:
        return False
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    # Header text is latin-1, and compare_digest rejects non-ASCII str.
    return hmac.compare_digest(
        credentials.strip().encode("latin-1"), token.encode()
    )
