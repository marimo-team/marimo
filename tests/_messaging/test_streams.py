import sys

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

    @staticmethod
    async def test_getpass_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [exec_req.get("import getpass; output = getpass.getpass('pwd: ')")]
        )
        assert k.globals["output"] == "pwd: "


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


class TestStrSubclassCoercion:
    """Verify str subclasses (e.g. loguru Message) are coerced to plain str."""

    @staticmethod
    async def test_stdout_str_subclass(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    """
                    import sys

                    class _TaggedStr(str):
                        pass

                    _msg = _TaggedStr("tagged hello")
                    _msg.extra = {"key": "value"}
                    sys.stdout.write(_msg)
                    """
                )
            ]
        )
        assert mocked_kernel.stdout.messages == ["tagged hello"]
        for m in mocked_kernel.stdout.messages:
            assert type(m) is str

    @staticmethod
    async def test_stderr_str_subclass(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    """
                    import sys

                    class _TaggedStr(str):
                        pass

                    _msg = _TaggedStr("tagged error")
                    _msg.record = {"level": "ERROR"}
                    sys.stderr.write(_msg)
                    """
                )
            ]
        )
        assert mocked_kernel.stderr.messages == ["tagged error"]
        for m in mocked_kernel.stderr.messages:
            assert type(m) is str


async def test_import_multiprocessing(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    # https://github.com/marimo-team/marimo/issues/684
    #
    # On Windows this also guards against the pytest-spawn interaction:
    # __main__.__file__ must not point at the pytest.exe zipapp, or the
    # Manager child's multiprocessing.spawn._fixup_main_from_path will
    # runpy.run_path() pytest itself and the parent hangs on reader.recv().
    # See the _fake_main_file fixture in tests/conftest.py.
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
