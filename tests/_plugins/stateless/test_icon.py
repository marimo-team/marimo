# Copyright 2024 Marimo. All rights reserved.

from marimo._plugins.stateless.icon import icon


def test_mo_icon() -> None:
    assert (
        icon("lucide:leaf").text
        == "<iconify-icon icon='lucide:leaf' inline></iconify-icon>"
    )

    expected = (
        "<iconify-icon icon='lucide:leaf' width='32px' height='32px' inline>"
        + "</iconify-icon>"
    )

    assert icon("lucide:leaf", size=32).text == expected

    expected = (
        "<iconify-icon icon='lucide:leaf' inline style='color: red'>"
        + "</iconify-icon>"
    )
    assert icon("lucide:leaf", color="red").text == expected

    assert (
        icon("lucide:leaf", inline=False).text
        == "<iconify-icon icon='lucide:leaf'></iconify-icon>"
    )

    expected = (
        "<iconify-icon icon='lucide:leaf' inline flip='horizontal'>"
        + "</iconify-icon>"
    )

    assert icon("lucide:leaf", flip="horizontal").text == expected
