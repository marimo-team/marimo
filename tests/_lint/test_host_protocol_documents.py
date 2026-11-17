# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import pytest
from openapi_spec_validator import validate

from tests.utils import host_openapi


@pytest.mark.parametrize("experimental", [False, True])
def test_documents_are_valid_openapi(experimental: bool) -> None:
    validate(host_openapi(experimental=experimental))
