# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import uuid

import pytest  # noqa: F401

from marimo._messaging.context import (
    HTTP_REQUEST_CTX,
    RUN_ID_CTX,
    http_request_context,
    run_id_context,
)
from marimo._runtime.requests import HTTPRequest


class TestRunIDContext:
    def test_run_id_context_manager(self) -> None:
        # Test that run_id_context sets and unsets the run ID
        with run_id_context() as ctx:
            # Run ID should be set within the context
            run_id = RUN_ID_CTX.get()
            assert run_id is not None
            assert isinstance(run_id, str)

            # Should be a valid UUID
            uuid_obj = uuid.UUID(run_id)
            assert str(uuid_obj) == run_id

        # Run ID should be unset outside the context
        with pytest.raises(LookupError):
            RUN_ID_CTX.get()

    def test_run_id_context_generates_unique_ids(self) -> None:
        # Test that run_id_context generates unique IDs
        with run_id_context() as ctx1:
            run_id1 = RUN_ID_CTX.get()

            with run_id_context() as ctx2:
                run_id2 = RUN_ID_CTX.get()

                # IDs should be different
                assert run_id1 != run_id2

            # Should restore the outer context
            assert RUN_ID_CTX.get() == run_id1

        # Run ID should be unset outside the context
        with pytest.raises(LookupError):
            RUN_ID_CTX.get()


class TestHTTPRequestContext:
    def test_http_request_context_manager_with_request(self) -> None:
        # Test that http_request_context sets and unsets the HTTP request
        request = HTTPRequest(
            url={
                "path": "/test",
                "port": None,
                "scheme": "http",
                "netloc": "localhost",
                "query": "",
                "hostname": "localhost",
            },
            base_url={
                "path": "",
                "port": None,
                "scheme": "http",
                "netloc": "localhost",
                "query": "",
                "hostname": "localhost",
            },
            headers={},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )

        with http_request_context(request):
            # Request should be set within the context
            ctx_request = HTTP_REQUEST_CTX.get()
            assert ctx_request is not None
            assert ctx_request is request
            assert ctx_request.url["path"] == "/test"

        # Request should be unset outside the context
        with pytest.raises(LookupError):
            HTTP_REQUEST_CTX.get()

    def test_http_request_context_manager_with_none(self) -> None:
        # Test that http_request_context can set None
        with http_request_context(None):
            # Request should be None within the context
            ctx_request = HTTP_REQUEST_CTX.get()
            assert ctx_request is None

        # Request should be unset outside the context
        with pytest.raises(LookupError):
            HTTP_REQUEST_CTX.get()

    def test_nested_http_request_contexts(self) -> None:
        # Test nested http_request_contexts
        request1 = HTTPRequest(
            url={
                "path": "/test1",
                "port": None,
                "scheme": "http",
                "netloc": "localhost",
                "query": "",
                "hostname": "localhost",
            },
            base_url={
                "path": "",
                "port": None,
                "scheme": "http",
                "netloc": "localhost",
                "query": "",
                "hostname": "localhost",
            },
            headers={},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )

        request2 = HTTPRequest(
            url={
                "path": "/test2",
                "port": None,
                "scheme": "http",
                "netloc": "localhost",
                "query": "",
                "hostname": "localhost",
            },
            base_url={
                "path": "",
                "port": None,
                "scheme": "http",
                "netloc": "localhost",
                "query": "",
                "hostname": "localhost",
            },
            headers={},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )

        with http_request_context(request1):
            # Outer context should have request1
            assert HTTP_REQUEST_CTX.get() is request1

            with http_request_context(request2):
                # Inner context should have request2
                assert HTTP_REQUEST_CTX.get() is request2

            # Should restore the outer context
            assert HTTP_REQUEST_CTX.get() is request1

        # Request should be unset outside the context
        with pytest.raises(LookupError):
            HTTP_REQUEST_CTX.get()
