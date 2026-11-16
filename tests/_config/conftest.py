# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_config_environment(clean_config_environment: None) -> None:
    pass
