# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import uuid

import pytest

from marimo._messaging.context import (
    HTTP_REQUEST_CTX,
    RUN_ID_CTX,
    http_request_context,
    run_id_context,
)
from marimo._runtime.requests import HTTPRequest


class TestMessagingContextVarsRunID:
    def test_run_id_is_uuid(self):
        with run_id_context():
            run_id = RUN_ID_CTX.get()
            # Verify it's a valid UUID string
            assert uuid.UUID(run_id)

    def test_nested_contexts(self):
        with run_id_context():
            outer_id = RUN_ID_CTX.get()
            with run_id_context():
                inner_id = RUN_ID_CTX.get()
                assert inner_id != outer_id

            # Verify we're back to outer context
            assert RUN_ID_CTX.get() == outer_id

    def test_context_cleanup(self):
        # Verify context is None before entering
        with pytest.raises(LookupError):
            RUN_ID_CTX.get()

        with run_id_context():
            assert RUN_ID_CTX.get() is not None

        # Verify context is cleaned up after exiting
        with pytest.raises(LookupError):
            RUN_ID_CTX.get()


class TestMessagingContextVarsHTTP:
    @pytest.fixture
    def mock_request(self):
        return HTTPRequest(
            url={"path": "/test"},
            base_url={"path": "/"},
            path_params={},
            cookies={},
            user={"is_authenticated": True},
            headers={},
            query_params={},
            meta={},
        )

    def test_http_request_context(self, mock_request: HTTPRequest):
        with http_request_context(mock_request):
            assert HTTP_REQUEST_CTX.get() == mock_request

    def test_nested_contexts(self, mock_request: HTTPRequest):
        request2 = HTTPRequest(
            url={"path": "/test2"},
            base_url={"path": "/"},
            path_params={},
            cookies={},
            user={"is_authenticated": True},
            headers={},
            query_params={},
            meta={},
        )

        with http_request_context(mock_request):
            outer_req = HTTP_REQUEST_CTX.get()
            with http_request_context(request2):
                inner_req = HTTP_REQUEST_CTX.get()
                assert inner_req != outer_req
                assert inner_req == request2

            # Verify we're back to outer context
            assert HTTP_REQUEST_CTX.get() == outer_req

    def test_context_cleanup(self, mock_request: HTTPRequest):
        # Verify context is None before entering
        with pytest.raises(LookupError):
            HTTP_REQUEST_CTX.get()

        with http_request_context(mock_request):
            assert HTTP_REQUEST_CTX.get() == mock_request

        # Verify context is cleaned up after exiting
        with pytest.raises(LookupError):
            HTTP_REQUEST_CTX.get()

    def test_none_request(self):
        with http_request_context(None):
            assert HTTP_REQUEST_CTX.get() is None
