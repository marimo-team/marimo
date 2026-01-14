from __future__ import annotations

import multiprocessing as mp
import threading
import time
from contextlib import contextmanager

import pytest

from marimo._utils.file_lock import ReadWriteLock, Timeout


@pytest.fixture(scope="session", autouse=True)
def set_multiprocessing_start_method():
    """Set multiprocessing start method to 'spawn' for the entire test session."""
    # Set start method once for the entire test session
    # Ensure it's only set if not already set or if the current method is different
    if mp.get_start_method(allow_none=True) != "spawn":
        mp.set_start_method("spawn", force=True)


# Helper function to run in a separate process to acquire a read lock
def acquire_read_lock(
    lock_file,
    acquired_event,
    release_event=None,
    timeout=-1,
    blocking=True,
    ready_event=None,
) -> bool | None:
    # Get error queue from current process if available
    current_process = mp.current_process()
    error_queue = getattr(current_process, "_error_queue", None)

    if ready_event:
        ready_event.wait(timeout=10)

    try:
        lock = ReadWriteLock(lock_file, timeout=timeout, blocking=blocking)
        with lock.read_lock():
            acquired_event.set()
            if release_event:
                # Wait for signal to release if provided
                release_event.wait(timeout=10)
            else:
                # Hold the lock for a short time
                time.sleep(0.5)
        return True
    except Timeout:
        return False
    except Exception as e:
        import traceback

        error_msg = f"Read lock process error: {e}\n{traceback.format_exc()}"
        if error_queue:
            error_queue.put(error_msg)
        return False


# Helper function to run in a separate process to acquire a write lock
def acquire_write_lock(
    lock_file,
    acquired_event,
    release_event=None,
    timeout=-1,
    blocking=True,
    ready_event=None,
) -> bool | None:
    if ready_event:
        ready_event.wait(timeout=10)

    try:
        lock = ReadWriteLock(lock_file, timeout=timeout, blocking=blocking)
        with lock.write_lock():
            acquired_event.set()
            if release_event:
                # Wait for signal to release if provided
                release_event.wait(timeout=10)
            else:
                # Hold the lock for a short time
                time.sleep(0.5)
        return True
    except Timeout:
        return False
    except Exception:
        return False


# Helper function to try upgrading a read lock to a write lock (should fail)
def try_upgrade_lock(
    lock_file, read_acquired_event, upgrade_attempted_event, upgrade_result
) -> None:
    lock = ReadWriteLock(lock_file)
    try:
        with lock.read_lock():
            read_acquired_event.set()
            time.sleep(0.2)  # Ensure the read lock is established

            # Now try to acquire a write lock (should fail)
            upgrade_attempted_event.set()
            try:
                with lock.write_lock(timeout=0.5):
                    upgrade_result.value = 1  # Succeeded (shouldn't happen)
            except RuntimeError:
                upgrade_result.value = 0  # Expected failure
            except Timeout:
                upgrade_result.value = 2  # Timeout (unexpected)
            except Exception:
                upgrade_result.value = 3  # Other error
    except Exception:
        upgrade_result.value = 4


# Helper function to try downgrading a write lock to a read lock (should fail)
def try_downgrade_lock(
    lock_file,
    write_acquired_event,
    downgrade_attempted_event,
    downgrade_result,
) -> None:
    lock = ReadWriteLock(lock_file)
    try:
        with lock.write_lock():
            write_acquired_event.set()
            time.sleep(0.2)  # Ensure the write lock is established

            # Now try to acquire a read lock (should fail)
            downgrade_attempted_event.set()
            try:
                with lock.read_lock(timeout=0.5):
                    downgrade_result.value = 1  # Succeeded (shouldn't happen)
            except RuntimeError:
                downgrade_result.value = 0  # Expected failure
            except Timeout:
                downgrade_result.value = 2  # Timeout (unexpected)
            except Exception:
                downgrade_result.value = 3  # Other error
    except Exception:
        downgrade_result.value = 4


@contextmanager
def cleanup_processes(processes):
    error_queue = mp.Queue()
    for p in processes:
        # Store the queue in process for later retrieval
        p._error_queue = error_queue

    try:
        yield error_queue
    finally:
        # Wait for processes to finish first (important!)
        for p in processes:
            if p.is_alive():
                # Give a chance to finish normally before terminating
                p.join(timeout=0.1)
            if p.is_alive():
                p.terminate()
            # Join again after potential terminate
            p.join(timeout=1)

        # Check for errors *after* trying to join/terminate
        errors = []
        try:
            while True:
                errors.append(error_queue.get(block=False))
        except mp.queues.Empty:
            pass

        if errors:
            pytest.fail(
                "Errors occurred in subprocess(es):\n"
                + "\n---\n".join(errors),
                pytrace=False,
            )


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "test_lock.db")


@pytest.mark.timeout(20)
def test_read_locks_are_shared(lock_file) -> None:
    """Test that multiple processes can acquire read locks simultaneously."""
    # Create shared events
    read1_acquired = mp.Event()
    read2_acquired = mp.Event()

    # Start two processes that acquire read locks
    p1 = mp.Process(target=acquire_read_lock, args=(lock_file, read1_acquired))
    p2 = mp.Process(target=acquire_read_lock, args=(lock_file, read2_acquired))

    with cleanup_processes([p1, p2]):
        p1.start()
        time.sleep(0.1)  # Give p1 a chance to start acquiring
        p2.start()

        # Both processes should be able to acquire read locks
        assert read1_acquired.wait(timeout=2), (
            f"First read lock not acquired on {lock_file}"
        )
        assert read2_acquired.wait(timeout=2), (
            f"Second read lock not acquired on {lock_file}"
        )

        # Wait for processes to finish
        p1.join(timeout=2)
        p2.join(timeout=2)
        assert not p1.is_alive(), "Process 1 did not exit cleanly"
        assert not p2.is_alive(), "Process 2 did not exit cleanly"


@pytest.mark.timeout(20)
def test_write_lock_excludes_other_write_locks(lock_file) -> None:
    """Test that a write lock prevents other processes from acquiring write locks."""
    # Create shared events
    write1_acquired = mp.Event()
    release_write1 = mp.Event()
    write2_acquired = mp.Event()

    # Start first process to acquire write lock
    p1 = mp.Process(
        target=acquire_write_lock,
        args=(lock_file, write1_acquired, release_write1),
    )

    # Second process will try to acquire with a short timeout
    # We'll restart it after the first process releases the lock
    p2 = mp.Process(
        target=acquire_write_lock,
        args=(lock_file, write2_acquired, None, 0.5, True),
    )

    with cleanup_processes([p1]):
        p1.start()
        assert write1_acquired.wait(timeout=2), "First write lock not acquired"

        # Second process should not be able to acquire write lock
        with cleanup_processes([p2]):
            p2.start()
            assert not write2_acquired.wait(timeout=1), (
                "Second write lock should not be acquired"
            )

            # Release first write lock
            release_write1.set()
            p1.join(timeout=2)
            assert not p1.is_alive(), "Process 1 did not exit cleanly"

        # Create a new process to try acquiring the lock now that it's released
        write2_acquired.clear()  # Reset the event
        p3 = mp.Process(
            target=acquire_write_lock, args=(lock_file, write2_acquired, None)
        )

        with cleanup_processes([p3]):
            p3.start()
            # Now the new process should be able to acquire the lock
            assert write2_acquired.wait(timeout=2), (
                "Second write lock not acquired after first released"
            )
            p3.join(timeout=2)
            assert not p3.is_alive(), "Process 3 did not exit cleanly"


@pytest.mark.timeout(20)
def test_write_lock_excludes_read_locks(lock_file) -> None:
    """Test that a write lock prevents other processes from acquiring read locks."""
    # Create shared events
    write_acquired = mp.Event()
    release_write = mp.Event()
    read_acquired = mp.Event()
    read_started = mp.Event()  # New event to signal when read attempt starts

    # Start process to acquire write lock
    p1 = mp.Process(
        target=acquire_write_lock,
        args=(lock_file, write_acquired, release_write),
    )

    # Start process to try to acquire read lock with no timeout
    # Use a ready_event to control when the read lock attempt should start
    p2 = mp.Process(
        target=acquire_read_lock,
        args=(lock_file, read_acquired, None, -1, True, read_started),
    )

    with cleanup_processes([p1, p2]):
        p1.start()
        assert write_acquired.wait(timeout=2), "Write lock not acquired"

        # Start the read process but don't signal it to begin acquiring yet
        p2.start()

        # Now signal p2 to attempt acquiring the read lock
        read_started.set()

        # Wait a short time - read lock should NOT be acquired while write lock is held
        time.sleep(2)
        assert not read_acquired.is_set(), (
            "Read lock should not be acquired while write lock held"
        )

        # Release write lock
        release_write.set()
        p1.join(timeout=2)

        # Now read process should be able to acquire the lock
        assert read_acquired.wait(timeout=2), (
            "Read lock not acquired after write released"
        )

        p2.join(timeout=2)
        assert not p2.is_alive(), "Process 2 did not exit cleanly"


@pytest.mark.timeout(20)
def test_read_lock_excludes_write_locks(lock_file) -> None:
    """Test that read locks prevent other processes from acquiring write locks."""
    # Create shared events
    read_acquired = mp.Event()
    release_read = mp.Event()
    write_acquired = mp.Event()
    write_started = mp.Event()  # New event to signal when write attempt starts

    # Start process to acquire read lock
    p1 = mp.Process(
        target=acquire_read_lock, args=(lock_file, read_acquired, release_read)
    )

    # Start process to try to acquire write lock with no timeout
    # Use a ready_event to control when the write lock attempt should start
    p2 = mp.Process(
        target=acquire_write_lock,
        args=(lock_file, write_acquired, None, -1, True, write_started),
    )

    with cleanup_processes([p1, p2]):
        p1.start()
        assert read_acquired.wait(timeout=2), "Read lock not acquired"

        # Start the write process but don't signal it to begin acquiring yet
        p2.start()

        # Now signal p2 to attempt acquiring the write lock
        write_started.set()

        # Wait a short time - write lock should NOT be acquired while read lock is held
        time.sleep(2)
        assert not write_acquired.is_set(), (
            "Write lock should not be acquired while read lock held"
        )

        # Release read lock
        release_read.set()
        p1.join(timeout=2)

        # Now write process should be able to acquire the lock
        assert write_acquired.wait(timeout=2), (
            "Write lock not acquired after read released"
        )

        p2.join(timeout=2)
        assert not p2.is_alive(), "Process 2 did not exit cleanly"


# Move this function to module level (before the test functions)
def chain_reader(
    idx,
    lock_file,
    release_count,
    forward_wait,
    backward_wait,
    forward_set,
    backward_set,
) -> None:
    # Wait for signal to start acquiring
    forward_wait.wait(timeout=10)

    try:
        lock = ReadWriteLock(lock_file)
        with lock.read_lock():
            if idx > 0:
                # Don't make all read locks set off immediately via the forward_set
                # chain.
                time.sleep(2)

            # Signal next reader to start if not the last one
            if forward_set is not None:
                forward_set.set()

            if idx == 0:
                # Hold off releasing the write lock process (backward_set is writer_ready at idx=0)
                time.sleep(1)

            backward_set.set()

            # Wait for a signal from the next read to release, so that there is
            # always a read lock holding. Non-starvating write lock from another
            # process must make this backward_wait to timeout, actually.
            backward_wait.wait(timeout=10)

            # Increment the release counter before releasing
            with release_count.get_lock():
                release_count.value += 1

    except Exception as e:
        import traceback

        error_msg = f"Reader process error: {e}\n{traceback.format_exc()}"
        current_process = mp.current_process()
        error_queue = getattr(current_process, "_error_queue", None)
        if error_queue:
            error_queue.put(error_msg)


@pytest.mark.timeout(40)
def test_write_non_starvation(lock_file) -> None:
    """Test that write locks can eventually be acquired even with continuous read locks.

    Creates a chain of reader processes where the writer starts after the first reader
    acquires a lock. The writer should be able to acquire its lock before the entire
    reader chain has finished, demonstrating non-starvation.
    """
    NUM_READERS = 7

    # Create events for coordination
    chain_forward = [
        mp.Event() for _ in range(NUM_READERS)
    ]  # Signal to start acquiring
    chain_backward = [
        mp.Event() for _ in range(NUM_READERS)
    ]  # Signal to release
    writer_ready = mp.Event()
    writer_acquired = mp.Event()

    # Shared counter to track how many readers have released
    release_count = mp.Value("i", 0)

    # Create reader processes
    readers = []
    for i in range(NUM_READERS):
        forward_set = chain_forward[i + 1] if i < NUM_READERS - 1 else None
        backward_set = chain_backward[i - 1] if i > 0 else writer_ready
        reader = mp.Process(
            target=chain_reader,
            args=(
                i,
                lock_file,
                release_count,
                chain_forward[i],
                chain_backward[i],
                forward_set,
                backward_set,
            ),
        )
        readers.append(reader)

    # Create writer process that will try to acquire after first reader is established
    writer = mp.Process(
        target=acquire_write_lock,
        args=(lock_file, writer_acquired, None, 20, True, writer_ready),
    )

    with cleanup_processes([*readers, writer]):
        # Start all reader processes (they'll wait for their start signal)
        for reader in readers:
            reader.start()

        # Signal the first reader to start
        chain_forward[0].set()

        # Wait a bit for the first reader to acquire and signal the writer
        assert writer_ready.wait(timeout=10), (
            "First reader did not acquire lock"
        )

        # Start the writer process (it will wait for writer_ready event)
        writer.start()

        assert writer_acquired.wait(timeout=22), (
            "Writer couldn't acquire lock - possible starvation"
        )

        with release_count.get_lock():
            read_releases = release_count.value

        assert read_releases < 3, (
            f"Writer acquired after {read_releases} readers released - this indicates starvation"
        )

        # Wait for writer to finish
        writer.join(timeout=2)
        assert not writer.is_alive(), "Writer did not exit cleanly"

        # Let the last reader release
        chain_backward[-1].set()

        # Wait for all readers to finish
        for idx, reader in enumerate(readers):
            reader.join(timeout=3)
            assert not reader.is_alive(), f"Reader {idx} did not exit cleanly"


# Move this function to module level (before the test functions)
def recursive_read_lock(lock_file, success_flag) -> None:
    lock = ReadWriteLock(lock_file)
    try:
        with lock.read_lock():
            # First acquisition
            assert lock._thread_local.reentrancy_level == 1
            assert lock._thread_local.mode == "read"

            with lock.read_lock():
                # Second acquisition
                assert lock._thread_local.reentrancy_level == 2
                assert lock._thread_local.mode == "read"

                with lock.read_lock():
                    # Third acquisition
                    assert lock._thread_local.reentrancy_level == 3
                    assert lock._thread_local.mode == "read"

                # After third release
                assert lock._thread_local.reentrancy_level == 2
                assert lock._thread_local.mode == "read"

            # After second release
            assert lock._thread_local.reentrancy_level == 1
            assert lock._thread_local.mode == "read"

        # After first release
        assert lock._thread_local.reentrancy_level == 0
        assert lock._thread_local.mode is None

        success_flag.value = 1
    except Exception:
        success_flag.value = 0


@pytest.mark.timeout(10)
def test_recursive_read_lock_acquisition(lock_file) -> None:
    """Test that the same process can acquire the same read lock multiple times."""
    success = mp.Value("i", 0)
    p = mp.Process(target=recursive_read_lock, args=(lock_file, success))

    with cleanup_processes([p]):
        p.start()
        p.join(timeout=5)

    assert success.value == 1, "Recursive read lock acquisition failed"


# Move this function to module level (before the test functions)
def recursive_write_lock(lock_file, success_flag) -> None:
    lock = ReadWriteLock(lock_file)
    try:
        with lock.write_lock():
            # First acquisition
            assert lock._thread_local.reentrancy_level == 1
            assert lock._thread_local.mode == "write"

            with lock.write_lock():
                # Second acquisition
                assert lock._thread_local.reentrancy_level == 2
                assert lock._thread_local.mode == "write"

                with lock.write_lock():
                    # Third acquisition
                    assert lock._thread_local.reentrancy_level == 3
                    assert lock._thread_local.mode == "write"

                # After third release
                assert lock._thread_local.reentrancy_level == 2
                assert lock._thread_local.mode == "write"

            # After second release
            assert lock._thread_local.reentrancy_level == 1
            assert lock._thread_local.mode == "write"

        # After first release
        assert lock._thread_local.reentrancy_level == 0
        assert lock._thread_local.mode is None

        success_flag.value = 1
    except Exception:
        success_flag.value = 0


@pytest.mark.timeout(10)
def test_recursive_write_lock_acquisition(lock_file) -> None:
    """Test that the same process can acquire the same write lock multiple times."""
    success = mp.Value("i", 0)
    p = mp.Process(target=recursive_write_lock, args=(lock_file, success))

    with cleanup_processes([p]):
        p.start()
        p.join(timeout=5)

    assert success.value == 1, "Recursive write lock acquisition failed"


def acquire_write_lock_and_crash(lock_file, acquired_event) -> None:
    lock = ReadWriteLock(lock_file)
    with lock.write_lock():
        acquired_event.set()
        # Simulate process crash with infinite loop
        while True:
            time.sleep(0.1)


@pytest.mark.timeout(15)
def test_write_lock_release_on_process_termination(lock_file) -> None:
    """Test that write locks are properly released if a process terminates."""
    # Create shared events
    lock_acquired = mp.Event()

    # Start a process that will acquire the lock and then "crash"
    p1 = mp.Process(
        target=acquire_write_lock_and_crash, args=(lock_file, lock_acquired)
    )
    p1.start()

    # Wait for lock to be acquired
    assert lock_acquired.wait(timeout=2), "Lock not acquired by first process"

    # Create second process that will try to acquire the lock
    write_acquired = mp.Event()
    p2 = mp.Process(
        target=acquire_write_lock, args=(lock_file, write_acquired)
    )

    with cleanup_processes([p1, p2]):
        # Terminate the first process (simulating a crash)
        time.sleep(0.5)  # Ensure lock is fully acquired
        p1.terminate()
        p1.join(timeout=2)

        # Start second process - should be able to acquire the lock
        p2.start()

        # Check if second process can acquire the lock
        assert write_acquired.wait(timeout=5), (
            "Lock not acquired after process termination"
        )

        p2.join(timeout=2)
        assert not p2.is_alive(), "Second process did not exit cleanly"


def acquire_read_lock_and_crash(lock_file, acquired_event) -> None:
    lock = ReadWriteLock(lock_file)
    with lock.read_lock():
        acquired_event.set()
        # Simulate process crash with infinite loop
        while True:
            time.sleep(0.1)


@pytest.mark.timeout(15)
def test_read_lock_release_on_process_termination(lock_file) -> None:
    """Test that readlocks are properly released if a process terminates."""
    # Create shared events
    lock_acquired = mp.Event()

    # Start a process that will acquire the lock and then "crash"
    p1 = mp.Process(
        target=acquire_read_lock_and_crash, args=(lock_file, lock_acquired)
    )
    p1.start()

    # Wait for lock to be acquired
    assert lock_acquired.wait(timeout=2), "Lock not acquired by first process"

    # Create second process that will try to acquire the lock
    write_acquired = mp.Event()
    p2 = mp.Process(
        target=acquire_write_lock, args=(lock_file, write_acquired)
    )

    with cleanup_processes([p1, p2]):
        # Terminate the first process (simulating a crash)
        time.sleep(0.5)  # Ensure lock is fully acquired
        p1.terminate()
        p1.join(timeout=2)

        # Start second process - should be able to acquire the lock
        p2.start()

        # Check if second process can acquire the lock
        assert write_acquired.wait(timeout=5), (
            "Lock not acquired after process termination"
        )

        p2.join(timeout=2)
        assert not p2.is_alive(), "Second process did not exit cleanly"


@pytest.mark.timeout(15)
def test_single_read_lock_acquire_release(lock_file) -> None:
    """Test that a single read lock can be acquired and released."""
    # Create a lock
    lock = ReadWriteLock(lock_file)

    # Acquire and release a read lock
    with lock.read_lock():
        # Lock is acquired here
        assert True, "Read lock acquired"
        # Let's verify we can read the same lock again (read locks are reentrant)
        with lock.read_lock():
            assert True, "Read lock acquired again"

    # Lock should be released here
    # We can test this by acquiring it again
    with lock.read_lock():
        assert True, "Read lock can be acquired after release"


@pytest.mark.timeout(15)
def test_single_write_lock_acquire_release(lock_file) -> None:
    """Test that a single write lock can be acquired and released."""
    # Create a lock
    lock = ReadWriteLock(lock_file)

    # Acquire and release a write lock
    with lock.write_lock():
        # Lock is acquired here
        assert True, "Write lock acquired"
        # Let's verify we can write lock again (write locks are reentrant)
        with lock.write_lock():
            assert True, "Write lock acquired again"

    # Lock should be released here
    # We can test this by acquiring it again
    with lock.write_lock():
        assert True, "Write lock can be acquired after release"


@pytest.mark.timeout(15)
def test_read_then_write_lock(lock_file) -> None:
    """Test that we can acquire a read lock and then a write lock after releasing it."""
    lock = ReadWriteLock(lock_file)

    # First acquire a read lock
    with lock.read_lock():
        assert True, "Read lock acquired"

    # After releasing the read lock, we should be able to acquire a write lock
    with lock.write_lock():
        assert True, "Write lock acquired after read lock released"


@pytest.mark.timeout(15)
def test_write_then_read_lock(lock_file) -> None:
    """Test that we can acquire a write lock and then a read lock after releasing it."""
    lock = ReadWriteLock(lock_file)

    # First acquire a write lock
    with lock.write_lock():
        assert True, "Write lock acquired"

    # After releasing the write lock, we should be able to acquire a read lock
    with lock.read_lock():
        assert True, "Read lock acquired after write lock released"


@pytest.mark.timeout(10)
def test_timeout_behavior(lock_file) -> None:
    """Test that timeout parameter works correctly in multi-process environment."""
    # Create shared events
    write_acquired = mp.Event()
    release_write = mp.Event()
    read_acquired = mp.Event()

    # Start process to acquire write lock and hold it
    p1 = mp.Process(
        target=acquire_write_lock,
        args=(lock_file, write_acquired, release_write),
    )

    # Start process to try to acquire read lock with timeout
    p2 = mp.Process(
        target=acquire_read_lock,
        args=(lock_file, read_acquired, None, 0.5, True),
    )

    with cleanup_processes([p1, p2]):
        p1.start()
        assert write_acquired.wait(timeout=2), "Write lock not acquired"

        # Start timer to measure timeout
        start_time = time.time()
        p2.start()

        # Process should not acquire read lock and should exit after timeout
        assert not read_acquired.wait(timeout=1), (
            "Read lock should not be acquired"
        )
        p2.join(timeout=5)  # Allow more time for joining

        # Verify timeout duration was approximately correct
        # Make the timing constraints more reasonable
        elapsed = time.time() - start_time
        assert 0.4 <= elapsed <= 2.0, f"Timeout was not respected: {elapsed}s"

        # Clean up
        release_write.set()
        p1.join(timeout=2)


@pytest.mark.timeout(10)
def test_non_blocking_behavior(lock_file) -> None:
    """Test that non-blocking parameter works correctly.

    This test directly attempts to acquire a read lock in non-blocking mode
    when a write lock is already held by another process.
    """
    # Create shared events for the write lock
    write_acquired = mp.Event()
    release_write = mp.Event()

    # Start process to acquire write lock and hold it
    p1 = mp.Process(
        target=acquire_write_lock,
        args=(lock_file, write_acquired, release_write),
    )

    with cleanup_processes([p1]):
        p1.start()
        assert write_acquired.wait(timeout=2), "Write lock not acquired"

        lock = ReadWriteLock(lock_file)

        # Start timer to measure how quickly non-blocking returns
        start_time = time.time()

        # Attempt to acquire a read lock in non-blocking mode
        try:
            with lock.read_lock(blocking=False):
                # Should never reach here
                pytest.fail("Non-blocking read lock was unexpectedly acquired")
        except Timeout:
            # Expected behavior - lock acquisition should fail immediately
            pass

        elapsed = time.time() - start_time

        # Non-blocking should return very quickly
        assert elapsed < 0.1, f"Non-blocking took too long: {elapsed}s"

        # Clean up
        release_write.set()
        p1.join(timeout=2)


@pytest.mark.timeout(10)
def test_lock_upgrade_prohibited(lock_file) -> None:
    """Test that a process cannot upgrade from a read lock to a write lock."""
    read_acquired = mp.Event()
    upgrade_attempted = mp.Event()
    upgrade_result = mp.Value("i", -1)

    p = mp.Process(
        target=try_upgrade_lock,
        args=(lock_file, read_acquired, upgrade_attempted, upgrade_result),
    )

    with cleanup_processes([p]):
        p.start()

        # Wait for read lock to be acquired
        assert read_acquired.wait(timeout=2), "Read lock not acquired"

        # Wait for upgrade to be attempted
        assert upgrade_attempted.wait(timeout=2), "Upgrade not attempted"

        # Wait for process to finish
        p.join(timeout=2)
        assert not p.is_alive(), "Process did not exit cleanly"

        # Verify result
        assert upgrade_result.value == 0, (
            "Read lock was incorrectly upgraded to write lock"
        )


@pytest.mark.timeout(10)
def test_lock_downgrade_prohibited(lock_file) -> None:
    """Test that a process cannot downgrade from a write lock to a read lock."""
    write_acquired = mp.Event()
    downgrade_attempted = mp.Event()
    downgrade_result = mp.Value("i", -1)

    p = mp.Process(
        target=try_downgrade_lock,
        args=(
            lock_file,
            write_acquired,
            downgrade_attempted,
            downgrade_result,
        ),
    )

    with cleanup_processes([p]):
        p.start()

        # Wait for write lock to be acquired
        assert write_acquired.wait(timeout=2), "Write lock not acquired"

        # Wait for downgrade to be attempted
        assert downgrade_attempted.wait(timeout=2), "Downgrade not attempted"

        # Wait for process to finish
        p.join(timeout=2)
        assert not p.is_alive(), "Process did not exit cleanly"

        # Verify result
        assert downgrade_result.value == 0, (
            "Write lock was incorrectly downgraded to read lock"
        )


@pytest.mark.timeout(10)
def test_threaded_read_locks_shared(lock_file) -> None:
    """Test that multiple threads can acquire read locks simultaneously."""
    lock = ReadWriteLock(lock_file)

    # Use events for synchronization
    thread1_acquired = threading.Event()
    thread2_acquired = threading.Event()
    threads_can_release = threading.Event()

    # Define thread functions
    def thread_read_lock_1():
        with lock.read_lock():
            thread1_acquired.set()
            threads_can_release.wait(timeout=5)

    def thread_read_lock_2():
        with lock.read_lock():
            thread2_acquired.set()
            threads_can_release.wait(timeout=5)

    # Start threads
    t1 = threading.Thread(target=thread_read_lock_1)
    t2 = threading.Thread(target=thread_read_lock_2)

    t1.start()
    # Wait for first thread to acquire read lock
    assert thread1_acquired.wait(timeout=2), (
        "First thread couldn't acquire read lock"
    )

    t2.start()
    # Second thread should also be able to acquire read lock
    assert thread2_acquired.wait(timeout=2), (
        "Second thread couldn't acquire read lock"
    )

    # Release threads
    threads_can_release.set()

    # Wait for threads to finish
    t1.join(timeout=2)
    t2.join(timeout=2)

    assert not t1.is_alive() and not t2.is_alive(), (
        "Threads did not exit cleanly"
    )


@pytest.mark.timeout(10)
def test_threaded_write_locks_exclusive(lock_file) -> None:
    """Test that write locks are exclusive between threads."""
    lock = ReadWriteLock(lock_file)

    # Use events for synchronization
    write1_acquired = threading.Event()
    write1_released = threading.Event()
    write2_attempted = threading.Event()
    write2_acquired = threading.Event()

    # Define thread functions
    def thread_write_lock_1():
        with lock.write_lock():
            write1_acquired.set()
            # Hold the lock until signaled
            write1_released.wait(timeout=5)

    def thread_write_lock_2():
        write2_attempted.set()
        # Try to acquire with timeout
        try:
            with lock.write_lock(timeout=0.5):
                write2_acquired.set()
        except Timeout:
            pass

    # Start first thread and wait for it to acquire
    t1 = threading.Thread(target=thread_write_lock_1)
    t1.start()
    assert write1_acquired.wait(timeout=2), (
        "First thread couldn't acquire write lock"
    )

    # Start second thread
    t2 = threading.Thread(target=thread_write_lock_2)
    t2.start()

    # Wait for second thread to attempt acquiring
    assert write2_attempted.wait(timeout=2), (
        "Second thread didn't attempt to acquire"
    )

    # Give some time for potential acquisition (should not happen)
    time.sleep(1)
    assert not write2_acquired.is_set(), (
        "Second thread shouldn't acquire write lock while first holds it"
    )

    # Release first thread's lock
    write1_released.set()

    # Wait for threads to finish
    t1.join(timeout=2)
    t2.join(timeout=2)

    assert not t1.is_alive() and not t2.is_alive(), (
        "Threads did not exit cleanly"
    )


@pytest.mark.timeout(10)
def test_singleton_behavior(lock_file) -> None:
    """Test that locks with the same path use the same instance."""
    lock1 = ReadWriteLock(lock_file)
    lock2 = ReadWriteLock(lock_file)

    # Same path should return the same instance
    assert lock1 is lock2, "Locks with same path should be the same instance"

    # Different paths should return different instances
    lock3 = ReadWriteLock(lock_file + ".different")
    assert lock1 is not lock3, (
        "Locks with different paths should be different instances"
    )

    # Parameter mismatch should raise ValueError
    with pytest.raises(ValueError):
        ReadWriteLock(
            lock_file, timeout=5
        )  # Different timeout than the original


@pytest.mark.timeout(10)
def test_non_singleton_behavior(lock_file) -> None:
    """Test that non-singleton locks can be created independently."""
    lock1 = ReadWriteLock(lock_file, is_singleton=False)
    lock2 = ReadWriteLock(lock_file, is_singleton=False)

    # Same path with is_singleton=False should return different instances
    assert lock1 is not lock2, (
        "Non-singleton locks should be different instances"
    )

    # Test that they still coordinate via the underlying file lock
    thread1_acquired = threading.Event()
    thread1_ready_to_release = threading.Event()
    thread2_attempted = threading.Event()
    thread2_acquired = threading.Event()

    def thread_acquire_write_lock1():
        with lock1.write_lock():
            thread1_acquired.set()
            thread1_ready_to_release.wait(timeout=5)

    def thread_acquire_write_lock2():
        thread2_attempted.set()
        try:
            with lock2.write_lock(timeout=0.5):
                thread2_acquired.set()
        except Timeout:
            pass

    t1 = threading.Thread(target=thread_acquire_write_lock1)
    t2 = threading.Thread(target=thread_acquire_write_lock2)

    t1.start()
    assert thread1_acquired.wait(timeout=2), (
        "First thread couldn't acquire write lock"
    )

    t2.start()
    assert thread2_attempted.wait(timeout=2), (
        "Second thread didn't attempt to acquire"
    )

    # Give time for potential acquisition (should not happen while t1 holds lock)
    time.sleep(1)
    assert not thread2_acquired.is_set(), (
        "Second lock instance shouldn't acquire while first holds lock"
    )

    # Release first lock
    thread1_ready_to_release.set()

    # Wait for threads to finish
    t1.join(timeout=2)
    t2.join(timeout=2)

    assert not t1.is_alive() and not t2.is_alive(), (
        "Threads did not exit cleanly"
    )


@pytest.mark.timeout(10)
def test_exception_safety(lock_file) -> None:
    """Test that locks are released when exceptions occur in the with block."""
    lock = ReadWriteLock(lock_file)

    # Test read lock exception safety
    try:
        with lock.read_lock():
            raise ValueError("Test exception")
    except ValueError:
        pass

    # If read lock was properly released, we should be able to acquire a write lock
    with lock.write_lock(timeout=0.1):
        pass

    # Test write lock exception safety
    try:
        with lock.write_lock():
            raise ValueError("Test exception")
    except ValueError:
        pass

    # If write lock was properly released, we should be able to acquire a read lock
    with lock.read_lock(timeout=0.1):
        pass
