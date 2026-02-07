import sys

import pytest

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider, MockedKernel


# Make sure that standard in is installed; stdin is not writable so we
# just check that its methods are callable and return mocked values.
class TestStdin:
    @staticmethod
    async def test_encoding(mocked_kernel: MockedKernel) -> None:
        assert mocked_kernel.stdin.encoding == sys.stdin.encoding

    @staticmethod
    async def test_input_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run([exec_req.get("output = input('hello')")])
        assert k.globals["output"] == "hello"

    @staticmethod
    async def test_readline_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [exec_req.get("import sys; output = sys.stdin.readline()")]
        )
        assert k.globals["output"] == ""

    @staticmethod
    async def test_readlines_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [exec_req.get("import sys; output = sys.stdin.readlines()")]
        )
        assert k.globals["output"] == [""]


class TestStdout:
    @staticmethod
    async def test_encoding(mocked_kernel: MockedKernel) -> None:
        assert mocked_kernel.stdout.encoding == sys.stdout.encoding

    @staticmethod
    async def test_fileno(k: Kernel, exec_req: ExecReqProvider) -> None:
        await k.run([exec_req.get("import sys; fileno = sys.stdout.fileno()")])
        assert k.globals["fileno"] is not None

    @staticmethod
    async def test_print(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [exec_req.get("print('hello'); print('there')")]
        )
        assert mocked_kernel.stdout.messages == ["hello", "\n", "there", "\n"]

    @staticmethod
    async def test_write(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [exec_req.get("import sys; sys.stdout.write('hello')")]
        )
        assert mocked_kernel.stdout.messages == ["hello"]

    @staticmethod
    async def test_writelines(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    "import sys; sys.stdout.writelines(['hello', 'there'])"
                )
            ]
        )
        assert mocked_kernel.stdout.messages == ["hello", "there"]


class TestStderr:
    @staticmethod
    async def test_encoding(mocked_kernel: MockedKernel) -> None:
        assert mocked_kernel.stderr.encoding == sys.stderr.encoding

    @staticmethod
    async def test_fileno(k: Kernel, exec_req: ExecReqProvider) -> None:
        await k.run([exec_req.get("import sys; fileno = sys.stderr.fileno()")])
        assert k.globals["fileno"] is not None

    @staticmethod
    async def test_write(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [exec_req.get("import sys; sys.stderr.write('hello')")]
        )
        assert mocked_kernel.stderr.messages == ["hello"]

    @staticmethod
    async def test_writelines(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    "import sys; sys.stderr.writelines(['hello', 'there'])"
                )
            ]
        )
        assert mocked_kernel.stderr.messages == ["hello", "there"]


async def test_import_multiprocessing(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    # https://github.com/marimo-team/marimo/issues/684
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                from multiprocessing import Manager
                Manager().dict()
                print("hello")
                """
            )
        ]
    )
    assert mocked_kernel.stdout.messages == ["hello", "\n"]


class TestFdLevelStdout:
    """Tests for C library-style writes directly to the OS file descriptor.

    Reproduces https://github.com/marimo-team/marimo/issues/5536
    where C libraries writing to stdout via the OS file descriptor
    can kill the reader thread and cause subsequent cells to hang.
    """

    @staticmethod
    @pytest.mark.timeout(10)
    def test_forward_os_stream_survives_split_multibyte_utf8() -> None:
        """The _forward_os_stream reader thread must not die when a
        multi-byte UTF-8 character is split across read boundaries.

        This is the root cause of #5536: the reader thread calls
        data.decode() which raises UnicodeDecodeError for incomplete
        sequences. The bare except silently kills the thread. Then on
        the next cell execution, writes to the pipe block forever
        because nobody is draining it.
        """
        import os
        import threading
        import time

        from marimo._messaging.streams import _forward_os_stream

        # Collect all data written through the stream
        received: list[str] = []

        class FakeStream:
            def write(self, data: str) -> int:
                received.append(data)
                return len(data)

        read_fd, write_fd = os.pipe()
        should_exit = threading.Event()

        thread = threading.Thread(
            target=_forward_os_stream,
            args=(FakeStream(), read_fd, should_exit),
            daemon=True,
        )
        thread.start()

        # Write 1023 ASCII bytes + first byte of 'é' (U+00E9 = 0xC3 0xA9)
        # If os.read returns exactly 1024 bytes, decode() fails on \xc3
        data = b"A" * 1023 + b"\xc3"
        os.write(write_fd, data)
        # Write the second byte of 'é'
        os.write(write_fd, b"\xa9")
        # Write a marker so we know the thread processed everything
        os.write(write_fd, b"DONE")

        time.sleep(0.5)

        # The reader thread should still be alive
        assert thread.is_alive(), (
            "Reader thread died (likely from UnicodeDecodeError)"
        )

        # All data should have been forwarded (possibly merged differently)
        all_data = "".join(received)
        assert "DONE" in all_data, (
            f"Reader thread stopped processing data. Got: {all_data!r}"
        )

        # Cleanup
        should_exit.set()
        os.close(write_fd)
        thread.join(timeout=2)
        os.close(read_fd)

    @staticmethod
    @pytest.mark.timeout(10)
    def test_forward_os_stream_survives_invalid_utf8() -> None:
        """The reader thread must not die on completely invalid UTF-8 bytes."""
        import os
        import threading
        import time

        from marimo._messaging.streams import _forward_os_stream

        received: list[str] = []

        class FakeStream:
            def write(self, data: str) -> int:
                received.append(data)
                return len(data)

        read_fd, write_fd = os.pipe()
        should_exit = threading.Event()

        thread = threading.Thread(
            target=_forward_os_stream,
            args=(FakeStream(), read_fd, should_exit),
            daemon=True,
        )
        thread.start()

        # Write invalid UTF-8 bytes (standalone continuation bytes)
        os.write(write_fd, b"\x80\x81\x82\xff\xfe")
        # Write valid ASCII after the invalid bytes
        os.write(write_fd, b"AFTER")

        time.sleep(0.5)

        assert thread.is_alive(), "Reader thread died on invalid UTF-8 bytes"
        all_data = "".join(received)
        assert "AFTER" in all_data, (
            f"Reader thread stopped processing. Got: {all_data!r}"
        )

        # Cleanup
        should_exit.set()
        os.close(write_fd)
        thread.join(timeout=2)
        os.close(read_fd)

    @staticmethod
    @pytest.mark.timeout(10)
    async def test_fd_write_large_output_does_not_hang(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        """Large C library-style fd writes should not hang the cell."""
        # Get the fd that the watcher redirected (the original stdout fd)
        watcher = mocked_kernel.stdout._watcher
        target_fd = watcher.fd  # This is the fd that C libraries write to

        await mocked_kernel.k.run(
            [
                exec_req.get(
                    f"""
                    import os
                    # Simulate a C library writing lots of output with ANSI codes
                    chunk = b'\\x1b[1mBold text\\x1b[0m some output line\\n'
                    for _ in range(1000):
                        os.write({target_fd}, chunk)
                    result = "done"
                    """
                )
            ]
        )
        assert mocked_kernel.k.globals["result"] == "done"
