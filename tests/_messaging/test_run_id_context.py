import pytest

from marimo._messaging.context import RUN_ID_CTX, run_id_context


class TestRunIDContext:
    def test_run_id_context(self):
        with run_id_context():
            run_id = RUN_ID_CTX.get()
            assert run_id is not None, (
                "within run_id context but unable to obtain run_id"
            )

        # out of context manager
        with pytest.raises(LookupError):
            RUN_ID_CTX.get()
