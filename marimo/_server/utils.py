# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import errno
import os
import socket
import sys
from typing import TYPE_CHECKING, Any, TypeVar

from marimo import _loggers
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Optional

# use spaces instead of a tab to play well with carriage returns;
# \r\t doesn't appear to overwrite characters at the start of a line,
# but \r{TAB} does ...
TAB = "        "

LOGGER = _loggers.marimo_logger()


def print_tabbed(string: str, n_tabs: int = 1) -> None:
    print_(f"{TAB * n_tabs}{string}")


def canonicalize_filename(filename: str) -> str:
    # If its not a valid Python or Markdown file, then add .py
    if not MarimoPath.is_valid_path(filename):
        filename += ".py"
    return os.path.expanduser(filename)


_DEFAULT_BACKLOG = 128


# From Tornado (Apache 2.0)
# https://github.com/tornadoweb/tornado/blob/8a953697888d463f48090d500268892a7384e6b1/tornado/netutil.py#L56
def errno_from_exception(e: BaseException) -> Optional[int]:
    """Provides the errno from an Exception object.

    There are cases that the errno attribute was not set so we pull
    the errno out of the args but if someone instantiates an Exception
    without any args you will get a tuple error. So this function
    abstracts all that behavior to give you a safe way to get the
    errno.
    """

    if hasattr(e, "errno"):
        return e.errno  # type: ignore
    elif e.args:
        return e.args[0]  # type:ignore[no-any-return]
    else:
        return None


# From Tornado (Apache 2.0), battle-tested by Jupyter, streamlit, others
# https://github.com/tornadoweb/tornado/blob/8a953697888d463f48090d500268892a7384e6b1/tornado/netutil.py#L56
def bind_sockets(
    port: int,
    address: Optional[str] = None,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    backlog: int = _DEFAULT_BACKLOG,
    flags: int | None = None,
    reuse_port: bool = False,
) -> list[socket.socket]:
    """Creates listening sockets bound to the given port and address.

    Returns a list of socket objects (multiple sockets are returned if
    the given address maps to multiple IP addresses, which is most common
    for mixed IPv4 and IPv6 use).

    Address may be either an IP address or hostname.  If it's a hostname,
    the server will listen on all IP addresses associated with the
    name.  Address may be an empty string or None to listen on all
    available interfaces.  Family may be set to either `socket.AF_INET`
    or `socket.AF_INET6` to restrict to IPv4 or IPv6 addresses, otherwise
    both will be used if available.

    The ``backlog`` argument has the same meaning as for
    `socket.listen() <socket.socket.listen>`.

    ``flags`` is a bitmask of AI_* flags to `~socket.getaddrinfo`, like
    ``socket.AI_PASSIVE | socket.AI_NUMERICHOST``.

    ``reuse_port`` option sets ``SO_REUSEPORT`` option for every socket
    in the list. If your platform doesn't support this option ValueError will
    be raised.
    """
    if reuse_port and not hasattr(socket, "SO_REUSEPORT"):
        raise ValueError("the platform doesn't support SO_REUSEPORT")

    sockets = []
    if address == "":
        address = None
    if not socket.has_ipv6 and family == socket.AF_UNSPEC:
        # Python can be compiled with --disable-ipv6, which causes
        # operations on AF_INET6 sockets to fail, but does not
        # automatically exclude those results from getaddrinfo
        # results.
        # http://bugs.python.org/issue16208
        family = socket.AF_INET
    if flags is None:
        flags = socket.AI_PASSIVE
    bound_port = None
    unique_addresses = set()  # type:ignore[type-arg]
    for res in sorted(
        socket.getaddrinfo(
            address, port, family, socket.SOCK_STREAM, 0, flags
        ),
        key=lambda x: x[0],
    ):
        if res in unique_addresses:
            continue

        unique_addresses.add(res)

        af, socktype, proto, _, sockaddr = res
        if (
            sys.platform == "darwin"
            and address == "localhost"
            and af == socket.AF_INET6
            and sockaddr[3] != 0  # type: ignore
        ):
            # Mac OS X includes a link-local address fe80::1%lo0 in the
            # getaddrinfo results for 'localhost'.  However, the firewall
            # doesn't understand that this is a local address and will
            # prompt for access (often repeatedly, due to an apparent
            # bug in its ability to remember granting access to an
            # application). Skip these addresses.
            continue
        try:
            sock = socket.socket(af, socktype, proto)
        except OSError as e:
            if errno_from_exception(e) == errno.EAFNOSUPPORT:
                continue
            raise
        if os.name != "nt":
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except OSError as e:
                if errno_from_exception(e) != errno.ENOPROTOOPT:
                    # Hurd doesn't support SO_REUSEADDR.
                    raise
        if reuse_port:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        if af == socket.AF_INET6:
            # On linux, ipv6 sockets accept ipv4 too by default,
            # but this makes it impossible to bind to both
            # 0.0.0.0 in ipv4 and :: in ipv6.  On other systems,
            # separate sockets *must* be used to listen for both ipv4
            # and ipv6.  For consistency, always disable ipv4 on our
            # ipv6 sockets and use a separate ipv4 socket when needed.
            #
            # Python 2.x on windows doesn't have IPPROTO_IPV6.
            if hasattr(socket, "IPPROTO_IPV6"):
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)

        # automatic port allocation with port=None
        # should bind on the same port on IPv4 and IPv6
        host, requested_port = sockaddr[:2]
        if requested_port == 0 and bound_port is not None:
            sockaddr = tuple([host, bound_port] + list(sockaddr[2:]))

        sock.setblocking(False)
        try:
            sock.bind(sockaddr)
        except OSError as e:
            if (
                errno_from_exception(e) == errno.EADDRNOTAVAIL
                and address == "localhost"
                and sockaddr[0] == "::1"
            ):
                # On some systems (most notably docker with default
                # configurations), ipv6 is partially disabled:
                # socket.has_ipv6 is true, we can create AF_INET6
                # sockets, and getaddrinfo("localhost", ...,
                # AF_PASSIVE) resolves to ::1, but we get an error
                # when binding.
                #
                # Swallow the error, but only for this specific case.
                # If EADDRNOTAVAIL occurs in other situations, it
                # might be a real problem like a typo in a
                # configuration.
                sock.close()
                continue
            else:
                raise
        bound_port = sock.getsockname()[1]
        sock.listen(backlog)
        sockets.append(sock)
    return sockets


def find_free_port(port: int, attempts: int = 100, addr: str = "") -> int:
    """Find a free port starting at `port`.

    Use addr="" or "0.0.0.0" to use all interfaces.
    """

    # Valid port range is 1-65535
    port = max(1, min(port, 65535))

    if attempts == 0:
        raise RuntimeError("Could not find a free port")

    # Based on logic from Jupyter server:
    # https://github.com/jupyter-server/jupyter_server/blob/56e2478a728ff292d8270e62d27dd50c316ee6b7/jupyter_server/serverapp.py#L2670
    try:
        sockets = bind_sockets(port, addr)
        sockets[0].close()
        return port
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            LOGGER.debug("Port %d already in use, trying another port.", port)
        elif e.errno in (
            errno.EACCES,
            getattr(errno, "WSAEACCES", errno.EACCES),
        ):
            LOGGER.warning("Permission to listen on port %d denied.", port)

    next_port = min(port + 1, 65535)
    if next_port == port:
        raise RuntimeError("No more ports available")

    return find_free_port(next_port, attempts - 1, addr=addr)


def initialize_mimetypes() -> None:
    import mimetypes

    # Fixes an issue with invalid mimetypes on windows:
    # https://github.com/encode/starlette/issues/829#issuecomment-587163696
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/svg+xml", ".svg")


def initialize_asyncio() -> None:
    """Platform-specific initialization of asyncio.

    Sessions use the `add_reader()` API, which is only available in the
    SelectorEventLoop policy; Windows uses the Proactor by default.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def initialize_fd_limit(limit: int) -> None:
    """Raise the limit on open file descriptors.

    Not applicable on Windows.
    """
    try:
        import resource
    except ImportError:
        # Windows
        return

    old_soft, old_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if limit > old_soft and limit <= old_hard:
        resource.setrlimit(resource.RLIMIT_NOFILE, (limit, old_hard))


T = TypeVar("T")


def asyncio_run(coro: Coroutine[Any, Any, T], **kwargs: dict[Any, Any]) -> T:
    """asyncio.run() with platform-specific initialization.

    When using Sessions, make sure to use this method instead of `asyncio.run`.

    If not using a Session, don't call this method.

    `kwargs` are passed to `asyncio.run()`
    """
    initialize_asyncio()
    return asyncio.run(coro, **kwargs)  # type: ignore[arg-type]


def print_(*args: Any, **kwargs: Any) -> None:
    try:
        import click

        click.echo(*args, **kwargs)
    except ImportError:
        print(*args, **kwargs)  # noqa: T201
