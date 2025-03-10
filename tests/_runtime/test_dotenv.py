from __future__ import annotations

import os
import tempfile

import pytest

from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies import DependencyManager
from marimo._runtime.requests import AppMetadata, CreationRequest
from marimo._runtime.runtime import Kernel


@pytest.mark.skipif(
    not DependencyManager.dotenv.has(), reason="dotenv is not installed"
)
class TestDotEnv:
    def test_load_dotenv_success(self, any_kernel: Kernel):
        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(suffix=".env", mode="w+") as env_file:
            env_file.write("TEST_VAR=test_value\n")
            env_file.write("ANOTHER_VAR=another_value\n")
            env_file.flush()

            # Create a custom config with the path to our temp .env file
            custom_config = DEFAULT_CONFIG.copy()
            custom_config["runtime"]["dotenv"] = [env_file.name]

            kernel = any_kernel

            # Load the .env file
            kernel.load_dotenv()

            # Check that the environment variables were set
            assert os.environ.get("TEST_VAR") == "test_value"
            assert os.environ.get("ANOTHER_VAR") == "another_value"

    def test_load_dotenv_nonexistent_file(self, any_kernel: Kernel):
        # Create a config with a nonexistent .env file
        custom_config = DEFAULT_CONFIG.copy()
        custom_config["runtime"]["dotenv"] = ["nonexistent.env"]

        # Create a kernel with our custom config
        kernel = any_kernel
        # This should not raise an exception
        kernel.load_dotenv()

    def test_load_dotenv_on_instantiate(self, monkeypatch: any):
        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(suffix=".env", mode="w+") as env_file:
            env_file.write("INSTANTIATE_TEST_VAR=instantiate_value\n")
            env_file.flush()

            # Create a custom config with the path to our temp .env file
            custom_config = DEFAULT_CONFIG.copy()
            custom_config["runtime"]["dotenv"] = [env_file.name]

            # Create a kernel with our custom config
            kernel = Kernel(
                cell_configs={},
                app_metadata=AppMetadata(
                    mode="edit", query_params={}, cli_args={}, request=None
                ),
                user_config=custom_config,
                stream=None,
                stdout=None,
                stderr=None,
                stdin=None,
                module=None,
                enqueue_control_request=lambda _: None,
            )

            # Mock the run method to prevent actually running cells
            monkeypatch.setattr(kernel, "run", lambda _: None)

            # Create a CreationRequest
            request = CreationRequest(
                execution_requests=[],
                set_ui_element_value_request=None,
                auto_run=True,
            )

            # Call instantiate, which should call load_dotenv
            kernel.instantiate(request)

            # Check that the environment variable was set
            assert (
                os.environ.get("INSTANTIATE_TEST_VAR") == "instantiate_value"
            )


@pytest.mark.skipif(
    DependencyManager.dotenv.has(), reason="dotenv should be installed"
)
class TestDotEnvNotInstalled:
    def test_load_dotenv_import_error(self, any_kernel: Kernel):
        kernel = any_kernel
        # This should not raise an exception
        kernel.load_dotenv()
