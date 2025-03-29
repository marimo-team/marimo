from __future__ import annotations

import os
import tempfile

from marimo._config.config import merge_default_config
from marimo._runtime.requests import (
    CreationRequest,
    SetUIElementValueRequest,
)
from tests.conftest import MockedKernel

# These tests work with and without python-dotenv installed.


def test_load_dotenv_success(mocked_kernel: MockedKernel):
    # Create a temporary .env file
    with tempfile.NamedTemporaryFile(suffix=".env", mode="w+") as env_file:
        env_file.write("TEST_VAR=test_value\n")
        env_file.write("ANOTHER_VAR=another_value\n")
        env_file.flush()

        # Create a custom config with the path to our temp .env file
        custom_config = merge_default_config(
            {
                "runtime": {
                    "dotenv": [env_file.name],
                },
            }
        )
        mocked_kernel.k.user_config = custom_config

        # Load the .env file
        mocked_kernel.k.load_dotenv()

        # Check that the environment variables were set
        assert os.environ.get("TEST_VAR") == "test_value"
        assert os.environ.get("ANOTHER_VAR") == "another_value"


def test_load_dotenv_nonexistent_file(mocked_kernel: MockedKernel):
    # Create a config with a nonexistent .env file
    custom_config = merge_default_config(
        {
            "runtime": {
                "dotenv": ["nonexistent.env"],
            },
        }
    )
    mocked_kernel.k.user_config = custom_config

    # Create a kernel with our custom config
    # This should not raise an exception
    mocked_kernel.k.load_dotenv()


async def test_load_dotenv_on_instantiate(mocked_kernel: MockedKernel):
    # Create a temporary .env file
    with tempfile.NamedTemporaryFile(suffix=".env", mode="w+") as env_file:
        env_file.write("INSTANTIATE_TEST_VAR=instantiate_value\n")
        env_file.flush()

        # Create a custom config with the path to our temp .env file
        custom_config = merge_default_config(
            {
                "runtime": {
                    "dotenv": [env_file.name],
                },
            }
        )
        mocked_kernel.k.user_config = custom_config

        # Create a CreationRequest
        request = CreationRequest(
            execution_requests=(),
            set_ui_element_value_request=SetUIElementValueRequest(
                object_ids=[],
                values=[],
            ),
            auto_run=True,
        )

        # Call instantiate, which should call load_dotenv
        await mocked_kernel.k.instantiate(request)

        # Check that the environment variable was set
        assert os.environ.get("INSTANTIATE_TEST_VAR") == "instantiate_value"
