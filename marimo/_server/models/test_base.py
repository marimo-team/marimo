# Copyright 2024 Marimo. All rights reserved.
from marimo._server.models.base import to_camel_case


def test_camel_case() -> None:
    assert to_camel_case("this_is_a_test") == "thisIsATest"
    assert to_camel_case("this") == "this"
    assert to_camel_case("this_is") == "thisIs"
    assert (
        to_camel_case("this_is_a_very_long_snake_case_string")
        == "thisIsAVeryLongSnakeCaseString"
    )
    assert to_camel_case("this_is_1_test") == "thisIs1Test"
    assert to_camel_case("") == ""
    assert to_camel_case("alreadyCamelCase") == "alreadyCamelCase"
    assert to_camel_case("With_Some_CAPS") == "withSomeCaps"
