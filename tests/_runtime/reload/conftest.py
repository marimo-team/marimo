import pytest
import reload_test_utils


@pytest.fixture
def py_modname() -> str:
    return reload_test_utils.random_modname()
