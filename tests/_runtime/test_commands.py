# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.commands import kebab_case


def test_kebab_case() -> None:
    assert kebab_case("SomeSQLCommand") == "some-sql"
    assert kebab_case("SomeSQL") == "some-sql"
    assert kebab_case("MyNotificationCommand") == "my-notification"
