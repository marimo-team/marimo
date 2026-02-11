# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import re
import shutil
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from _pytest import runner

from marimo._ast.app import App
from marimo._ast.app_config import _AppConfig
from marimo._ast.cell_manager import CellManager
from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import ConsoleMimeType
from marimo._messaging.notification import (
    CellNotification,
    NotificationMessage,
)
from marimo._messaging.print_override import print_override
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.streams import (
    ThreadSafeStderr,
    ThreadSafeStdin,
    ThreadSafeStdout,
    ThreadSafeStream,
)
from marimo._messaging.types import KernelMessage
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import patches
from marimo._runtime.commands import AppMetadata, ExecuteCellCommand
from marimo._runtime.context import teardown_context
from marimo._runtime.context.kernel_context import initialize_kernel_context
from marimo._runtime.input_override import input_override
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runner.hooks import create_default_hooks
from marimo._runtime.runtime import Kernel
from marimo._save.stubs.module_stub import ModuleStub
from marimo._server.utils import initialize_mimetypes
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import ModuleType

# register import hooks for third-party module formatters
register_formatters()

# Initialize mimetypes for consistent behavior across platforms (especially Windows)
initialize_mimetypes()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-skip tests based on @pytest.mark.requires() markers."""
    del config  # Unused but required by pytest hook signature
    for item in items:
        requires_marker = item.get_closest_marker("requires")
        if not requires_marker:
            continue

        missing_deps = []
        # Get dependency names from marker args
        for dep_name in requires_marker.args:
            # Try to get the dependency from DependencyManager
            dep_manager = getattr(DependencyManager, dep_name, None)
            if dep_manager is not None:
                if not dep_manager.has():
                    missing_deps.append(dep_name)
            else:
                # Unknown dependency name
                missing_deps.append(f"{dep_name} (unknown)")

        # Skip test if any dependencies are missing
        if missing_deps:
            deps_str = ", ".join(missing_deps)
            reason = f"requires {deps_str}"
            item.add_marker(pytest.mark.skip(reason=reason))


@pytest.fixture(autouse=True)
def patch_random_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch UIElement._random_seed to use a fixed seed for testing"""
    import random

    from marimo._plugins.ui._core.ui_element import UIElement

    # Patch the random seed to be deterministic for testing
    monkeypatch.setattr(UIElement, "_random_seed", random.Random(42))


@dataclasses.dataclass
class _MockStream(ThreadSafeStream):
    """Captures the ops sent through the stream"""

    cell_id: int | None = None
    input_queue: None = None
    pipe: None = None
    redirect_console: bool = False

    messages: list[KernelMessage] = dataclasses.field(default_factory=list)

    def write(self, data: KernelMessage) -> None:
        self.messages.append(data)
        # Attempt to deserialize the message to ensure it is valid
        deserialize_kernel_message(data)

    @property
    def operations(self) -> list[NotificationMessage]:
        return [
            deserialize_kernel_message(op_data) for op_data in self.messages
        ]

    @property
    def cell_notifications(self) -> list[CellNotification]:
        return [
            op for op in self.operations if isinstance(op, CellNotification)
        ]


class MockStdout(ThreadSafeStdout):
    """Captures the output sent through the stream"""

    def __init__(self, stream: _MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        del mimetype
        self.messages.append(data)
        return len(data)

    def __repr__(self) -> str:
        return "".join(self.messages)


class MockStderr(ThreadSafeStderr):
    """Captures the output sent through the stream"""

    messages: list[str] = dataclasses.field(default_factory=list)

    def __init__(self, stream: _MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        del mimetype
        self.messages.append(data)
        return len(data)

    def __repr__(self) -> str:
        # Error messages are commonly formatted for output in HTML
        return re.sub(r"<.*?>", "", "".join(self.messages))


class MockStdin(ThreadSafeStdin):
    """Echoes the prompt."""

    def __init__(self, stream: _MockStream) -> None:
        super().__init__(stream)
        self.messages: list[str] = []

    def _readline_with_prompt(self, prompt: str = "") -> str:
        return prompt


@dataclasses.dataclass
class MockedKernel:
    """Should only be created in fixtures b/c inits a runtime context"""

    stream: _MockStream = dataclasses.field(default_factory=_MockStream)
    session_mode: SessionMode = SessionMode.EDIT

    def __post_init__(self) -> None:
        self.stdout = MockStdout(self.stream)
        self.stderr = MockStderr(self.stream)
        self.stdin = MockStdin(self.stream)
        self._main = sys.modules["__main__"]
        module = patches.patch_main_module(
            file=None,
            input_override=input_override,
            print_override=print_override,
        )

        self.k = Kernel(
            stream=self.stream,
            stdout=self.stdout,
            stderr=self.stderr,
            stdin=self.stdin,
            cell_configs={},
            user_config=DEFAULT_CONFIG,
            app_metadata=AppMetadata(
                query_params={},
                filename=None,
                cli_args={},
                argv=None,
                app_config=_AppConfig(),
            ),
            debugger_override=MarimoPdb(stdout=self.stdout, stdin=self.stdin),
            enqueue_control_request=lambda _: None,
            module=module,
            hooks=create_default_hooks(),
        )

        initialize_kernel_context(
            kernel=self.k,
            stream=self.stream,  # type: ignore
            stdout=self.stdout,  # type: ignore
            stderr=self.stderr,  # type: ignore
            virtual_files_supported=True,
            mode=self.session_mode,
        )

    def teardown(self) -> None:
        # must be called by fixtures that instantiate this
        teardown_context()
        self.stdout._watcher.stop()
        self.stderr._watcher.stop()
        if self.k.module_watcher is not None:
            self.k.module_watcher.stop()
        sys.modules["__main__"] = self._main


# fixture that provides a kernel (and tears it down)
@pytest.fixture
def k() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    yield mocked.k
    mocked.teardown()


# kernel configured with runtime=lazy
@pytest.fixture
def lazy_kernel(k: Kernel) -> Kernel:
    k.execution_type = "relaxed"
    k.reactive_execution_mode = "lazy"
    return k


# kernel configured with strict execution
@pytest.fixture
def strict_kernel() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    mocked.k.execution_type = "strict"
    mocked.k.reactive_execution_mode = "autorun"
    yield mocked.k
    mocked.teardown()


# kernel configured in SessionMode.RUN mode
@pytest.fixture
def run_mode_kernel() -> Generator[MockedKernel, None, None]:
    mocked = MockedKernel(session_mode=SessionMode.RUN)
    yield mocked
    mocked.teardown()


@pytest.fixture(params=["k", "strict_kernel"])
def execution_kernel(request: Any) -> Kernel:
    return request.getfixturevalue(request.param)


@pytest.fixture(params=["k", "strict_kernel", "lazy_kernel"])
def any_kernel(request: Any) -> Kernel:
    return request.getfixturevalue(request.param)


# fixture that wraps a kernel and other mocked objects
@pytest.fixture
def mocked_kernel() -> Generator[MockedKernel, None, None]:
    mocked = MockedKernel()
    yield mocked
    mocked.teardown()


# Installs an execution context without stream redirection
@pytest.fixture
def executing_kernel() -> Generator[Kernel, None, None]:
    mocked = MockedKernel()
    mocked.k.stdout = None
    mocked.k.stderr = None
    mocked.k.stdin = None
    with mocked.k._install_execution_context(cell_id="0"):
        yield mocked.k
    mocked.teardown()


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_marimo_file(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook.py"
    tmp_file = tmp_path / "test" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_sandboxed_marimo_file(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook_sandboxed.py"
    tmp_file = tmp_path / "sandboxed" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_async_marimo_file(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook_async.py"
    tmp_file = tmp_path / "async" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_unparsable_marimo_file(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook_unparsable.py"
    tmp_file = tmp_path / "unparsable" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_marimo_file_with_md(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook_with_md.py"
    tmp_file = tmp_path / "with_md" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_marimo_file_with_media(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook_with_media.py"
    tmp_file = tmp_path / "with_media" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_md_marimo_file(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook.md"
    tmp_file = tmp_path / "with_md" / "notebook.md"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_marimo_file_with_errors(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook_with_errors.py"
    tmp_file = tmp_path / "with_errors" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


@pytest.fixture
def temp_marimo_file_with_multiple_definitions(tmp_path: Path) -> str:
    fixture_file = FIXTURE_DIR / "notebook_with_multiple_definitions.py"
    tmp_file = tmp_path / "with_multiple_definitions" / "notebook.py"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_file, tmp_file)
    return str(tmp_file)


# Factory to create ExecuteCellCommands and abstract away cell ID
class ExecReqProvider:
    def __init__(self) -> None:
        self.cell_manager = CellManager()

    def get(self, code: str) -> ExecuteCellCommand:
        key = self.cell_manager.create_cell_id()
        return ExecuteCellCommand(cell_id=key, code=textwrap.dedent(code))

    def get_with_id(self, cell_id: CellId_t, code: str) -> ExecuteCellCommand:
        return ExecuteCellCommand(cell_id=cell_id, code=textwrap.dedent(code))


# fixture that provides an ExecReqProvider
@pytest.fixture
def exec_req() -> ExecReqProvider:
    return ExecReqProvider()


# Library fixtures for direct marimo integration with pytest.
@pytest.fixture
def mo_fixture() -> ModuleType:
    import marimo as mo

    return mo


# Sets some non-public attributes on App and runs it.
@pytest.fixture
def app() -> Generator[App, None, None]:
    app = App()
    # Needed for consistent stack trace paths.
    app._anonymous_file = True
    # Provides verbose traceback on assertion errors. Note it does alter the
    # cell AST.
    app._pytest_rewrite = True
    yield app
    app.run()


class TestableModuleStub(ModuleStub):
    __test__ = False

    def __eq__(self, other: Any) -> bool:
        # Used for testing, equality otherwise not useful.
        if not isinstance(other, ModuleStub):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name) + hash("module")


# A pytest hook to fail when raw marimo cells are not collected.
# Meta testing gets a little messy, and may leave you a little testy. This is
# increasingly coupled with the following specific tests that test testing:
# _ast/
#    ./test_pytest
#    ./test_pytest_toplevel
#    ./test_pytest_scoped
@pytest.hookimpl
def pytest_make_collect_report(collector):
    # If it's not a module, we must early.
    if not isinstance(collector, pytest.Module):
        return None

    report = runner.pytest_make_collect_report(collector)

    # Defined within the file does not seem to hook correctly, as such filter
    # for the test_pytest specific file here.
    if not (
        "test_pytest" in str(collector.path) and "_ast" in str(collector.path)
    ):
        return report

    # Classes may also be registered, but they will be hidden behind a cell.
    # As such, let's just collect functions.
    collected = {
        fn.originalname
        for fn in collector.collect()
        if isinstance(fn, pytest.Function)
    }
    classes = {
        cls.name
        for cls in collector.collect()
        if isinstance(cls, pytest.Class)
    }
    from tests._ast.test_pytest import app as app_pytest
    from tests._ast.test_pytest_scoped import app as app_scoped
    from tests._ast.test_pytest_toplevel import app as app_toplevel

    app = {
        "test_pytest": app_pytest,
        "test_pytest_toplevel": app_toplevel,
        "test_pytest_scoped": app_scoped,
    }[collector.path.stem]

    # Just a quick check to make sure the class is actually exported.
    if app == app_pytest:
        if len(classes) == 0:
            report.outcome = "failed"
            report.longrepr = (
                f"Expected class in {collector.path}, found none "
                " (tests/conftest.py)."
            )
            return report
    for cls in classes:
        if not (
            cls.startswith("MarimoTestBlock")
            or cls
            in (
                "TestClassWorks",
                "TestClassWithFixtures",
                "TestClassDefinitionWithFixtures",
            )
        ):
            report.outcome = "failed"
            report.longrepr = (
                f"Unknown class '{cls}' in {collector.path}"
                " (tests/conftest.py)."
            )

            return report

    # Check the functions match cells in the app.
    invalid = []
    for name in app._cell_manager.names():
        if name.startswith("test_") and name not in collected:
            invalid.append(f"'{name}'")
    if invalid:
        tests = ", ".join([f"'{test}'" for test in collected])
        report.outcome = "failed"
        report.longrepr = (
            f"Cannot collect test(s) {', '.join(invalid)} from {tests}"
            " (tests/conftest.py)."
        )
    return report
