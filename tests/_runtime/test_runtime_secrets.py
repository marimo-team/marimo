from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from marimo._messaging.ops import SecretKeysResult
from marimo._runtime.requests import (
    ListSecretKeysRequest,
    RefreshSecretsRequest,
)
from marimo._runtime.runtime import SecretsCallbacks
from marimo._types.ids import RequestId
from tests._messaging.mocks import MockStream
from tests._runtime.test_runtime import MockedKernel


@pytest.fixture
def secrets_callbacks(mocked_kernel: MockedKernel):
    return SecretsCallbacks(mocked_kernel.k)


async def test_list_secrets_with_values(
    secrets_callbacks: SecretsCallbacks, mocked_kernel: MockedKernel
):
    # Set some test secrets
    test_secrets = ["DUMMY_SECRET"]
    os.environ["DUMMY_SECRET"] = "dummy-value"
    mocked_kernel.k._original_environ = os.environ.copy()

    await secrets_callbacks.list_secrets(
        ListSecretKeysRequest(request_id=RequestId("test"))
    )

    # Check that the broadcast message was sent with the correct secrets
    stream = MockStream(mocked_kernel.stream)
    secret_messages = [
        msg
        for msg in stream.parsed_operations
        if isinstance(msg, SecretKeysResult)
    ]
    assert len(secret_messages) == 1
    first_secret_message = secret_messages[0]
    assert first_secret_message.secrets[0].provider == "env"
    assert all(
        secret in first_secret_message.secrets[0].keys
        for secret in test_secrets
    )

    # Clean up
    for key in test_secrets:
        del os.environ[key]


async def test_refresh_secrets(
    secrets_callbacks: SecretsCallbacks, mocked_kernel: MockedKernel
):
    # Set some test secrets
    os.environ["DUMMY_SECRET"] = "dummy-value"
    mocked_kernel.k._original_environ = os.environ.copy()

    # Spy on load_dotenv method
    original_load_dotenv = mocked_kernel.k.load_dotenv
    mocked_kernel.k.load_dotenv = MagicMock(wraps=original_load_dotenv)

    await secrets_callbacks.refresh_secrets(RefreshSecretsRequest())

    # Check that load_dotenv was called
    assert mocked_kernel.k.load_dotenv.call_count == 1
