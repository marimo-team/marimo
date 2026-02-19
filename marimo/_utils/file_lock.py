# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Literal, Optional, Union
from weakref import WeakValueDictionary

from marimo import _loggers

_LOGGER = _loggers.marimo_logger()

# PRAGMA busy_timeout=N delegates to https://www.sqlite.org/c3ref/busy_timeout.html,
# which accepts an int argument, which has the maximum value of 2_147_483_647 on 32-bit
# systems. Use even a lower value to be safe. This 2 bln milliseconds is about 23 days.
_MAX_SQLITE_TIMEOUT_MS = 2_000_000_000 - 1


def timeout_for_sqlite(
    timeout: float, blocking: bool, already_waited: float
) -> int:
    """Calculates the timeout in milliseconds for SQLite's busy_timeout pragma."""
    if blocking is False:
        return 0  # `PRAGMA busy_timeout=0;` means non-blocking behaviour in SQLite

    if timeout == -1:
        return _MAX_SQLITE_TIMEOUT_MS

    if timeout < 0:
        msg = "timeout must be a non-negative number or -1"
        raise ValueError(msg)

    if already_waited >= timeout:
        return 0

    remaining_timeout = timeout - already_waited
    timeout_ms = remaining_timeout * 1000

    # Clamp to SQLite's maximum allowed value
    if timeout_ms > _MAX_SQLITE_TIMEOUT_MS:
        _LOGGER.warning(
            "Timeout %s (remaining %s) exceeds SQLite max; using %s ms.",
            timeout,
            remaining_timeout,
            _MAX_SQLITE_TIMEOUT_MS,
        )
        return _MAX_SQLITE_TIMEOUT_MS

    # Avoid busy_timeout=0 when the requested timeout is higher than zero but
    # less than 1 ms because it has non-blocking semantics.
    return max(1, int(timeout_ms))


class _ReadWriteLockMeta(type):
    """Metaclass that redirects instance creation to get_lock() when is_singleton=True."""

    def __call__(
        cls,
        lock_file: Union[str, os.PathLike[str]],
        timeout: float = -1,
        blocking: bool = True,
        is_singleton: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> ReadWriteLock:
        if is_singleton:
            # Pass only relevant args to get_lock
            return cls.get_lock(lock_file, timeout, blocking)
        # If not singleton, create directly, passing all args/kwargs
        return super().__call__(
            lock_file, timeout, blocking, is_singleton, *args, **kwargs
        )


# This is a helper class which is returned by :meth:`ReadWriteLock.acquire_read` and :meth:`ReadWriteLock.acquire_write`
# and wraps the lock to make sure __enter__ is not called twice when entering the with statement. If we would simply
# return *self*, the lock would be acquired again in the *__enter__* method of the ReadWriteLock, but not released
# again automatically.
class AcquireReturnProxy:
    """A context-aware object that will release the lock file when exiting."""

    def __init__(self, lock: ReadWriteLock) -> None:
        self.lock = lock

    def __enter__(self) -> ReadWriteLock:
        # Simply return the lock instance for use within the 'with' block
        return self.lock

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        # Ensure release is called when exiting the 'with' block
        self.lock.release()


class Timeout(Exception):
    """Exception raised when a lock cannot be acquired within the specified timeout."""

    def __init__(self, lock_file: Union[str, os.PathLike[str]]) -> None:
        self.lock_file = lock_file
        super().__init__(f"Timeout acquiring lock on {lock_file}")


class ReadWriteLock(metaclass=_ReadWriteLockMeta):
    """
    An inter-process and inter-thread read-write lock using SQLite transactions.

    Provides multiple-reader/single-writer semantics for a given lock file path.
    Also handles reentrancy correctly within the same thread.

    Features:
    - Cross-platform (relies on SQLite's file locking).
    - Supports blocking and non-blocking acquisition with timeouts.
    - Reentrant: A thread can acquire the same type of lock multiple times.
    - Default singleton behavior: `ReadWriteLock('path')` returns the same
      instance for the same absolute path within a process. Use
      `is_singleton=False` to create independent instances (and connections).

    Usage:
    - Explicit release required: Use the `read_lock()` or `write_lock()`
      context managers, or manually call `release()` in a `finally` block.
    - Explicit close recommended: Call `close()` when the lock is definitively
      no longer needed to release the SQLite connection and file handle.

    Limitation:
    - No lock upgrade (read -> write) or downgrade (write -> read) is allowed.

    Note on Singletons and Contention:
    The default singleton instance uses a single SQLite connection. Under heavy
    *intra-process* contention (many threads in the same process trying to
    acquire locks frequently), this single connection might become a bottleneck
    if threads block waiting for `PRAGMA busy_timeout`. If this occurs, consider
    creating separate instances using `ReadWriteLock(path, is_singleton=False)`.
    These separate instances still correctly coordinate both intra- and
    inter-process locking.
    """

    # Singleton storage and its lock.
    _instances: WeakValueDictionary[str, ReadWriteLock] = WeakValueDictionary()
    _instances_lock = threading.Lock()

    @classmethod
    def get_lock(
        cls,
        lock_file: Union[str, os.PathLike[str]],
        timeout: float = -1,
        blocking: bool = True,
    ) -> ReadWriteLock:
        """
        Return the singleton ReadWriteLock instance for a given file path.

        Ensures that all users of the lock file within the process share the
        same SQLite connection and intra-process thread signalling.

        Args:
            lock_file: The path to the file used for locking.
            timeout: Default timeout for acquire operations (-1 for infinite).
            blocking: Default blocking behavior for acquire operations.

        Raises:
            ValueError: If an existing singleton instance for this file was
                        created with different timeout/blocking parameters.
        """
        normalized = os.path.abspath(
            str(lock_file)
        )  # Ensure string for dict key
        with cls._instances_lock:
            instance = cls._instances.get(normalized)
            if instance is None:
                # Pass is_singleton=False to prevent recursion in __call__
                instance = super(_ReadWriteLockMeta, cls).__call__(
                    lock_file=lock_file,
                    timeout=timeout,
                    blocking=blocking,
                    is_singleton=False,
                )
                cls._instances[normalized] = instance
            elif instance.timeout != timeout or instance.blocking != blocking:
                # Check if parameters match the existing singleton
                msg = (
                    "Singleton lock for '%s' already exists with different "
                    "parameters (timeout=%s, blocking=%s). "
                    "Cannot recreate with (timeout=%s, blocking=%s)."
                )
                raise ValueError(
                    msg,
                    normalized,
                    instance.timeout,
                    instance.blocking,
                    timeout,
                    blocking,
                )
            # Ensure the existing instance isn't closed
            if instance._closed:
                _LOGGER.warning(
                    "Re-requesting a singleton lock that was already closed: %s",
                    normalized,
                )
                instance = super(_ReadWriteLockMeta, cls).__call__(
                    lock_file=lock_file,
                    timeout=timeout,
                    blocking=blocking,
                    is_singleton=False,
                )
                cls._instances[normalized] = instance

            return instance

    def __init__(
        self,
        lock_file: Union[str, os.PathLike[str]],
        timeout: float = -1,
        blocking: bool = True,
        is_singleton: bool = True,  # Parameter needed for metaclass logic
    ) -> None:
        self.lock_file = str(lock_file)
        self.timeout = timeout
        self.blocking = blocking

        # ReadWriteLock state protection
        self._internal_lock = threading.Lock()
        self._internal_lock_cond = threading.Condition(self._internal_lock)

        # ReadWriteLock state (protected by _internal_lock)
        self._current_mode: Optional[Literal["read", "write"]] = None
        # The number of threads currently holding a read lock *as known to this
        # ReadWriteLock instance only*. There could be more readers using
        # a different ReadWriteLock instance with the same lock file, within the
        # same or a different process.
        self._reader_count: int = 0
        self._acquisition_in_progress: bool = False
        self._acquisition_mode: Optional[Literal["read", "write"]] = None
        self._acquisition_blocking: Optional[bool] = None
        self._closed = False  # If the ReadWriteLock is closed

        # Per-thread state (reentrancy and mode)
        self._thread_local = threading.local()

        # SQLite connection and _journal_mode_set flag: accessed when
        # _internal_lock is not held, but because of the _acquisition_in_progress
        # control, only one thread can working with con and _journal_mode_set in
        # acquire_read() or acquire_write() at any time.
        #
        # check_same_thread=False is necessary because acquire/release might happen
        # in different threads, even though the actual SQLite calls within
        # acquire/release are serialized with the help of the _internal_lock.
        self.con = sqlite3.connect(self.lock_file, check_same_thread=False)
        # Track if PRAGMA journal_mode was set in either acquire_read() or acquire_write(),
        # called from any thread. We do it only once per ReadWriteLock instance
        # for performance.
        self._journal_mode_set = False

    def _ensure_thread_local_init(self) -> None:
        if self._thread_local.__dict__.get("reentrancy_level") is None:
            self._thread_local.reentrancy_level = 0
            self._thread_local.mode = None

    def _check_timeout(
        self, timeout: Optional[float], blocking: Optional[bool]
    ) -> tuple[float, bool]:
        _timeout = self.timeout if timeout is None else timeout
        _blocking = self.blocking if blocking is None else blocking

        # Check after applying defaults
        if _timeout < 0 and _timeout != -1:
            raise ValueError("timeout must be non-negative or -1")
        if _blocking and _timeout == 0:
            raise ValueError(
                "timeout must be positive or -1 if blocking is True"
            )

        return _timeout, _blocking

    def acquire_read(
        self, timeout: Optional[float] = None, blocking: Optional[bool] = None
    ) -> AcquireReturnProxy:
        """
        Acquire a read lock, waiting if necessary.

        Reentrant: Can be called multiple times by the same thread.
        Prohibited: Cannot acquire if the calling thread holds a write lock.

        Args:
            timeout: Override the instance's default timeout. -1 for infinite.
            blocking: Override the instance's default blocking behavior.

        Returns:
            An AcquireReturnProxy context manager object.

        Raises:
            Timeout: If the lock cannot be acquired within the timeout.
            RuntimeError: If the lock is closed or if attempting to downgrade
                          from a write lock held by the same thread.
            ValueError: If timeout is invalid.
        """
        timeout, blocking = self._check_timeout(timeout, blocking)

        self._ensure_thread_local_init()

        # --- Reentrancy and Downgrade Check ---
        if self._thread_local.mode == "read":
            self._thread_local.reentrancy_level += 1
            return AcquireReturnProxy(lock=self)
        if self._thread_local.mode == "write":
            raise RuntimeError(
                f"Cannot acquire read lock on {self.lock_file}: "
                "Thread already holds a write lock (downgrade forbidden)."
            )

        start_time: Optional[float] = None

        with self._internal_lock:
            # --- Wait for Conflicting Locks ---
            while not self._closed and (
                self._current_mode == "write" or self._acquisition_in_progress
            ):
                if not blocking:
                    if (
                        not self._acquisition_in_progress
                        or self._acquisition_mode == "write"
                        or self._acquisition_blocking
                    ):
                        raise Timeout(self.lock_file)
                    # If there are two threads entering acquire_read() simultaneously
                    # with blocking=False and the lock is available, it's unexpected
                    # that the other thread with fail with Timeout, so we will wait
                    # on _internal_lock_cond below, expecting that the other thread
                    # will exit acquire_read() quickly.

                if start_time is None:
                    start_time = time.perf_counter()
                    waited = 0.0
                else:
                    waited = time.perf_counter() - start_time

                if timeout == -1 or not blocking:
                    wait_for = None
                else:
                    if waited >= timeout:
                        raise Timeout(self.lock_file)
                    wait_for = timeout - waited
                self._internal_lock_cond.wait(timeout=wait_for)

            if self._closed:
                raise RuntimeError(f"Lock on {self.lock_file} is closed.")

            # Read lock is already held by another thread, quick acquisition
            # skipping SQLite.
            if self._current_mode == "read":
                self._reader_count += 1
                self._thread_local.mode = "read"
                self._thread_local.reentrancy_level = 1
                return AcquireReturnProxy(lock=self)

            self._acquisition_in_progress = True
            self._acquisition_mode = "read"
            self._acquisition_blocking = blocking

        # --- Acquire SQLite Lock (outside _internal_lock) ---
        # At this point, _current_mode should be None.

        sqlite_lock_acquired = False
        try:
            if start_time is None:
                start_time = time.perf_counter()
                waited = 0.0
            else:
                waited = time.perf_counter() - start_time
            timeout_ms = timeout_for_sqlite(timeout, blocking, waited)

            self.con.execute(f"PRAGMA busy_timeout={timeout_ms};")

            # Set journal mode only once per ReadWriteLock instance for performance/simplicity
            if not self._journal_mode_set:
                # WHY journal_mode=MEMORY?
                # Using the legacy journal mode rather than more modern WAL mode because,
                # apparently, in WAL mode it's impossible to enforce that read transactions
                # (started with BEGIN TRANSACTION) are blocked if a concurrent write transaction,
                # even EXCLUSIVE, is in progress, unless the read transactions actually read
                # any pages modified by the write transaction. But in the legacy journal mode,
                # it seems, it's possible to do this read-write locking without table data
                # modification at each exclusive lock.
                # See https://sqlite.org/lang_transaction.html#deferred_immediate_and_exclusive_transactions
                # "MEMORY" journal mode is fine because no actual writes to the are happening
                # in write-lock acquire, so crashes cannot adversely affect the DB.
                # Even journal_mode=OFF would probably be fine, too, but the SQLite documentation
                # says that ROLLBACK becomes *undefined behaviour* with journal_mode=OFF which
                # sounds scarier.
                #
                # WHY SETTING THIS PRAGMA HERE RATHER THAN IN ReadWriteLock.__init__()?
                # Because setting this pragma may block on the database if it is locked at the moment,
                # so we must set this pragma *after* `PRAGMA busy_timeout` above, and also
                # not in __init__() which is not expected to be blocked.
                self.con.execute("PRAGMA journal_mode=MEMORY;")
                self._journal_mode_set = True
                # Recompute the remaining timeout after the potentially blocking pragma
                # statement above.
                waited = time.perf_counter() - start_time
                timeout_ms_2 = timeout_for_sqlite(timeout, blocking, waited)
                if timeout_ms_2 != timeout_ms:
                    self.con.execute(f"PRAGMA busy_timeout={timeout_ms_2};")

            self.con.execute("BEGIN TRANSACTION;")
            # Need to make SELECT to compel SQLite to actually acquire a SHARED db lock.
            # See https://www.sqlite.org/lockingv3.html#transaction_control
            self.con.execute("SELECT name from sqlite_schema LIMIT 1;")

            # Set this variable for the `finally` block below
            sqlite_lock_acquired = True
            return AcquireReturnProxy(lock=self)

        except sqlite3.OperationalError as e:
            if "database is locked" not in str(e):
                raise  # Re-raise unexpected errors.
            raise Timeout(self.lock_file) from e
        finally:
            # --- Update Internal State (re-acquire _internal_lock) ---
            with self._internal_lock:
                self._acquisition_in_progress = False
                self._acquisition_mode = None
                self._acquisition_blocking = None
                if sqlite_lock_acquired:
                    self._current_mode = "read"
                    self._reader_count = 1
                    self._thread_local.mode = "read"
                    self._thread_local.reentrancy_level = 1

                self._internal_lock_cond.notify_all()

    def acquire_write(
        self, timeout: Optional[float] = None, blocking: Optional[bool] = None
    ) -> AcquireReturnProxy:
        """
        Acquire an exclusive write lock, waiting if necessary.

        Reentrant: Can be called multiple times by the same thread.
        Prohibited: Cannot acquire if the calling thread holds a read lock.

        Args:
            timeout: Override the instance's default timeout. -1 for infinite.
            blocking: Override the instance's default blocking behavior.

        Returns:
            An AcquireReturnProxy context manager object.

        Raises:
            Timeout: If the lock cannot be acquired within the timeout.
            RuntimeError: If the lock is closed or if attempting to upgrade
                          from a read lock held by the same thread.
            ValueError: If timeout is invalid.
        """
        timeout, blocking = self._check_timeout(timeout, blocking)

        self._ensure_thread_local_init()

        # --- Reentrancy and Upgrade Check ---
        if self._thread_local.mode == "write":
            # Already holding write lock, just increment reentrancy
            self._thread_local.reentrancy_level += 1
            return AcquireReturnProxy(lock=self)
        if self._thread_local.mode == "read":
            raise RuntimeError(
                f"Cannot acquire write lock on {self.lock_file}: "
                "Thread already holds a read lock (upgrade forbidden)."
            )

        start_time: Optional[float] = None

        with self._internal_lock:
            # --- Wait for Conflicting Locks ---
            # Wait if any lock is held (read or write)
            while not self._closed and (
                self._current_mode is not None or self._acquisition_in_progress
            ):
                if not blocking:
                    raise Timeout(self.lock_file)

                if start_time is None:
                    start_time = time.perf_counter()
                    waited = 0.0
                else:
                    waited = time.perf_counter() - start_time

                if timeout == -1:
                    wait_for = None
                else:
                    if waited >= timeout:
                        raise Timeout(self.lock_file)
                    wait_for = timeout - waited
                self._internal_lock_cond.wait(timeout=wait_for)

            if self._closed:
                raise RuntimeError(f"Lock on {self.lock_file} is closed.")

            self._acquisition_in_progress = True
            self._acquisition_mode = "write"
            self._acquisition_blocking = blocking

        # --- Acquire SQLite Lock (outside _internal_lock) ---
        # At this point, _current_mode should be None.

        sqlite_lock_acquired = False
        try:
            if start_time is None:
                start_time = time.perf_counter()
                waited = 0.0
            else:
                waited = time.perf_counter() - start_time
            timeout_ms = timeout_for_sqlite(timeout, blocking, waited)

            self.con.execute(f"PRAGMA busy_timeout={timeout_ms};")

            if not self._journal_mode_set:
                # For explanations for both why we use journal_mode=MEMORY and why we set
                # this pragma here rather than in ReadWriteLock.__init__(), see the comments
                # in acquire_read().
                self.con.execute("PRAGMA journal_mode=MEMORY;")
                self._journal_mode_set = True
                # Recompute the remaining timeout after the potentially blocking pragma
                # statement above.
                waited = time.perf_counter() - start_time
                timeout_ms_2 = timeout_for_sqlite(timeout, blocking, waited)
                if timeout_ms_2 != timeout_ms:
                    self.con.execute(f"PRAGMA busy_timeout={timeout_ms_2};")

            self.con.execute("BEGIN EXCLUSIVE TRANSACTION;")

            # Set this variable for the `finally` block below
            sqlite_lock_acquired = True
            return AcquireReturnProxy(lock=self)

        except sqlite3.OperationalError as e:
            if "database is locked" not in str(e):
                raise  # Re-raise unexpected errors.
            raise Timeout(self.lock_file) from e

        finally:
            # --- Update Internal State (re-acquire _internal_lock) ---
            with self._internal_lock:
                self._acquisition_in_progress = False
                self._acquisition_mode = None
                self._acquisition_blocking = None
                if sqlite_lock_acquired:
                    self._current_mode = "write"
                    self._thread_local.mode = "write"
                    self._thread_local.reentrancy_level = 1

                self._internal_lock_cond.notify_all()

    def release(self) -> None:
        """
        Releases the lock held by the current thread.

        Decrements the reentrancy level per-thread. If the level reaches zero, the
        thread's lock is fully released. If this was the last reader or the
        writer, the underlying SQLite lock is released.

        Raises:
            RuntimeError: If the lock is closed or if the current thread
                          does not hold the lock it's trying to release.
        """

        self._ensure_thread_local_init()

        if self._thread_local.mode is None:
            raise RuntimeError(
                f"Cannot release lock on {self.lock_file}: "
                "Lock not held by this thread."
            )

        level = self._thread_local.reentrancy_level - 1
        if level < 0:
            raise RuntimeError(
                f"Unexpected lock reentrancy level {level} for {self.lock_file}"
            )
        self._thread_local.reentrancy_level = level
        if level > 0:
            return  # Haven't unwinded the reentrancy stack per thread yet

        # Now level == 0, need to release the lock.
        mode = self._thread_local.mode
        self._thread_local.mode = None  # Clear thread-local state first

        with self._internal_lock:
            if self._closed:
                raise RuntimeError(f"Lock on {self.lock_file} is closed.")

            do_unlock = mode == "write"
            if mode == "read":
                count = self._reader_count - 1
                if count < 0:
                    raise RuntimeError(
                        f"Unexpected lock reader count {count} for {self.lock_file}"
                    )
                self._reader_count = count
                do_unlock = count == 0

            if do_unlock:
                self._current_mode = None
                self._internal_lock_cond.notify_all()
                try:
                    self.con.rollback()
                except sqlite3.Error as e:
                    # Any SQLite error is unexpected here. Try to consume it because
                    # The connection *might* be in a working state afterwards, or
                    # in the worst case the next call to acquire_read() or acquire_write()
                    # will fail as well.
                    _LOGGER.error(
                        "Unexpected error during SQLite rollback for %s: %s",
                        self.lock_file,
                        e,
                        exc_info=True,
                    )
                # Propagate other errors (such as I/O)

    def close(self) -> None:
        """
        Attempts to close the lock and the underlying SQLite connection.

        Idempotent: Calling multiple times has no effect after the first call.

        Raises:
            RuntimeError: If the lock is still held by any thread on this ReadWriteLock.
        """
        with self._internal_lock:
            if self._current_mode is not None:
                mode = self._thread_local.__dict__.get("mode")
                if mode is not None:
                    raise RuntimeError(
                        f"Lock on {self.lock_file} is held by the current thread "
                        f"in {mode} mode when close() is called. Confused close() with release()?"
                    )
                raise RuntimeError(
                    f"Lock on {self.lock_file} is still held when close()."
                )
            if self._acquisition_in_progress:
                raise RuntimeError(
                    f"Lock on {self.lock_file} is being acquired when close() is called."
                )

            if self._closed:
                return

            self._closed = True  # Mark as closed early

            # Notify any waiters that the lock is now defunct
            self._internal_lock_cond.notify_all()

            try:
                self.con.close()
            except (
                Exception
            ) as e:  # Try to make close() relatively quiet in term s
                _LOGGER.error(
                    "Error when closing SQLite connection for %s: %s",
                    self.lock_file,
                    e,
                    exc_info=True,
                )

        # Note: don't need to remove the ReadWriteLock instance from _instances
        # because get_lock() checks _closed flag and creates a new instance
        # if needed.

    # ----- Context Manager Protocol -----

    @contextmanager
    def read_lock(
        self, timeout: Optional[float] = None, blocking: Optional[bool] = None
    ):
        """
        Context manager for acquiring and releasing a read lock.

        Example:
            with lock.read_lock(timeout=5):
                # Read shared resource
                ...
        """
        self.acquire_read(timeout=timeout, blocking=blocking)
        try:
            yield
        finally:
            self.release()

    @contextmanager
    def write_lock(
        self, timeout: Optional[float] = None, blocking: Optional[bool] = None
    ):
        """
        Context manager for acquiring and releasing a write lock.

        Example:
            with lock.write_lock(blocking=False):
                # Modify shared resource
                ...
        """
        self.acquire_write(timeout=timeout, blocking=blocking)
        try:
            yield
        finally:
            self.release()
