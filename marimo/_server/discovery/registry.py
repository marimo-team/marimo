# Copyright 2026 Marimo. All rights reserved.
"""Secure filesystem publication for local discovery records."""

from __future__ import annotations

import atexit
import os
import stat
import sys
import tempfile
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._server.discovery.models import InstanceRecord

LOGGER = _loggers.marimo_logger()


def discovery_directory() -> Path:
    return marimo_state_dir() / "discovery" / "v1"


class DiscoveryRegistryWriter:
    """Atomically write and remove one private discovery record."""

    def __init__(self, record: InstanceRecord) -> None:
        self._record = record
        self._path = discovery_directory() / f"{record.id}.json"
        self._registered = False

    def register(self) -> None:
        directory = discovery_directory()
        _ensure_private_directories(directory)

        fd, temporary_path = tempfile.mkstemp(
            dir=str(directory), prefix=f".{self._record.id}.", suffix=".tmp"
        )
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            data = encode_json_bytes(self._record)
            remaining = memoryview(data)
            while remaining:
                written = os.write(fd, remaining)
                remaining = remaining[written:]
            os.fsync(fd)
            os.close(fd)
            fd = -1
            os.replace(temporary_path, self._path)
            if os.name == "nt":
                _verify_windows_private(self._path)
            else:
                _verify_posix_private_file(self._path)
        except Exception:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        self._registered = True
        atexit.register(self.deregister)
        LOGGER.debug("Registered local discovery publisher: %s", self._path)

    def deregister(self) -> None:
        if not self._registered:
            return
        try:
            self._path.unlink(missing_ok=True)
        except OSError as e:
            LOGGER.warning(
                "Failed to remove discovery record %s: %s", self._path, e
            )
        finally:
            self._registered = False


def _ensure_private_directories(directory: Path) -> None:
    if os.name == "nt" and not _windows_has_private_mkdir():
        raise PermissionError(
            "this Python version cannot create private discovery directories "
            "on Windows"
        )
    state_dir = directory.parent.parent
    state_dir.mkdir(parents=True, exist_ok=True)
    for path in (directory.parent, directory):
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        if os.name == "nt":
            _verify_windows_private(path)
        else:
            _verify_posix_private_directory(path)


def _verify_posix_private_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
        raise PermissionError(f"Discovery path is not a directory: {path}")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise PermissionError(
            f"Discovery directory has a different owner: {path}"
        )
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PermissionError(
            f"Discovery directory is accessible to other users: {path}"
        )


def _verify_posix_private_file(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise PermissionError(
            f"Discovery record is not a regular file: {path}"
        )
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise PermissionError(
            f"Discovery record has a different owner: {path}"
        )
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PermissionError(
            f"Discovery record is accessible to other users: {path}"
        )


def _windows_has_private_mkdir() -> bool:
    """Whether `os.mkdir(..., 0o700)` creates a private Windows DACL."""
    major, minor, micro = sys.version_info[:3]
    if (major, minor) == (3, 10):
        return micro >= 15
    if (major, minor) == (3, 11):
        return micro >= 10
    if (major, minor) == (3, 12):
        return micro >= 4
    return (major, minor) >= (3, 13)


def _verify_windows_private(path: Path) -> None:
    """Verify that every access-allowed ACE belongs to this user or Windows.

    Python's patched `mkdir(..., 0o700)` creates a protected DACL. We still
    inspect it because a pre-existing discovery directory may have been made
    by an older Python or another program. This uses only the standard
    library; discovery safely disables itself if inspection is unavailable.
    """
    if os.name != "nt":  # pragma: no cover - Windows-only implementation
        return
    if path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    ):
        raise PermissionError(f"Discovery path is a link: {path}")

    import ctypes
    from ctypes import wintypes

    class ACL_SIZE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("AceCount", wintypes.DWORD),
            ("AclBytesInUse", wintypes.DWORD),
            ("AclBytesFree", wintypes.DWORD),
        ]

    class ACE_HEADER(ctypes.Structure):
        _fields_ = [
            ("AceType", ctypes.c_ubyte),
            ("AceFlags", ctypes.c_ubyte),
            ("AceSize", wintypes.WORD),
        ]

    win_dll = ctypes.WinDLL  # type: ignore[attr-defined]
    advapi32 = win_dll("advapi32", use_last_error=True)
    kernel32 = win_dll("kernel32", use_last_error=True)

    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    advapi32.EqualSid.restype = wintypes.BOOL
    advapi32.GetAclInformation.argtypes = [
        ctypes.c_void_p,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    advapi32.GetAclInformation.restype = wintypes.BOOL
    advapi32.GetAce.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetAce.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    security_descriptor = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    owner = ctypes.c_void_p()

    # OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
    result = advapi32.GetNamedSecurityInfoW(
        str(path),
        1,  # SE_FILE_OBJECT
        0x00000001 | 0x00000004,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(security_descriptor),
    )
    if result != 0 or not dacl or not owner:
        if security_descriptor:
            kernel32.LocalFree(security_descriptor)
        raise PermissionError(f"Cannot inspect discovery ACL for {path}")

    token = wintypes.HANDLE()
    current_process = kernel32.GetCurrentProcess()
    if not advapi32.OpenProcessToken(
        current_process,
        0x0008,
        ctypes.byref(token),  # TOKEN_QUERY
    ):
        kernel32.LocalFree(security_descriptor)
        raise PermissionError("Cannot inspect the current Windows user")

    allocated_sids: list[ctypes.c_void_p] = []
    try:
        required = wintypes.DWORD()
        advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(required))
        token_info = ctypes.create_string_buffer(required.value)
        if not advapi32.GetTokenInformation(
            token,
            1,  # TokenUser
            token_info,
            required.value,
            ctypes.byref(required),
        ):
            raise PermissionError("Cannot read the current Windows user SID")
        current_user_sid = ctypes.c_void_p.from_buffer(token_info).value
        if current_user_sid is None:
            raise PermissionError("Current Windows user SID is missing")

        allowed_sids = [ctypes.c_void_p(current_user_sid)]
        for sid_string in ("S-1-5-18", "S-1-5-32-544"):
            sid = ctypes.c_void_p()
            if not advapi32.ConvertStringSidToSidW(
                sid_string, ctypes.byref(sid)
            ):
                raise PermissionError("Cannot construct a trusted Windows SID")
            allocated_sids.append(sid)
            allowed_sids.append(sid)

        if not any(advapi32.EqualSid(owner, sid) for sid in allowed_sids):
            raise PermissionError(
                f"Discovery path has an unexpected Windows owner: {path}"
            )

        acl_info = ACL_SIZE_INFORMATION()
        if not advapi32.GetAclInformation(
            dacl,
            ctypes.byref(acl_info),
            ctypes.sizeof(acl_info),
            2,  # AclSizeInformation
        ):
            raise PermissionError(f"Cannot inspect discovery ACL for {path}")

        for index in range(acl_info.AceCount):
            ace = ctypes.c_void_p()
            if not advapi32.GetAce(dacl, index, ctypes.byref(ace)):
                raise PermissionError(
                    f"Cannot inspect discovery ACL for {path}"
                )
            ace_address = ace.value
            if ace_address is None:
                raise PermissionError(
                    f"Cannot inspect discovery ACL for {path}"
                )
            header = ACE_HEADER.from_address(ace_address)
            if header.AceType == 1:  # ACCESS_DENIED_ACE_TYPE is safe
                continue
            if header.AceType != 0:  # Reject unfamiliar allow/callback ACEs
                raise PermissionError(
                    f"Discovery path has an unsupported Windows ACL: {path}"
                )
            ace_sid = ctypes.c_void_p(
                ace_address
                + ctypes.sizeof(ACE_HEADER)
                + ctypes.sizeof(wintypes.DWORD)
            )
            if not any(
                advapi32.EqualSid(ace_sid, sid) for sid in allowed_sids
            ):
                raise PermissionError(
                    f"Discovery path is accessible to another Windows user: {path}"
                )
    finally:
        kernel32.CloseHandle(token)
        for sid in allocated_sids:
            kernel32.LocalFree(sid)
        kernel32.LocalFree(security_descriptor)
