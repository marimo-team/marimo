# Copyright 2024 Marimo. All rights reserved.
from marimo._server.models.base import deep_to_camel_case, to_camel_case


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


def test_deep_to_camel_case() -> None:
    # Simple dictionary
    input_dict = {"first_key": "value1", "second_key": 2}
    expected_output = {"firstKey": "value1", "secondKey": 2}
    assert deep_to_camel_case(input_dict) == expected_output

    # Nested dictionary
    input_dict = {"outer_key": {"inner_key": "value"}}
    expected_output = {"outerKey": {"innerKey": "value"}}
    assert deep_to_camel_case(input_dict) == expected_output

    # List of dictionaries
    input_dict = {
        "list_key": [
            {"item_key": "item_value"},
            {"item_key_2": "item_value_2"},
        ]
    }
    expected_output = {
        "listKey": [{"itemKey": "item_value"}, {"itemKey2": "item_value_2"}]
    }
    assert deep_to_camel_case(input_dict) == expected_output

    # Mixed types and nested structures
    input_dict = {
        "first_level": {
            "second_level": [
                {"third_level_key_1": "value1"},
                {"third_level_key_2": "value2"},
            ],
            "another_second_level": "value",
        }
    }
    expected_output = {
        "firstLevel": {
            "secondLevel": [
                {"thirdLevelKey1": "value1"},
                {"thirdLevelKey2": "value2"},
            ],
            "anotherSecondLevel": "value",
        }
    }
    assert deep_to_camel_case(input_dict) == expected_output
