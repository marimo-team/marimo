from __future__ import annotations

import pytest

from marimo._plugins.stateless.nav_menu import (
    NavMenu,
    NavMenuItemGroup,
    NavMenuItemLink,
    _build_and_validate_menu,
)


def test_build_and_validate_menu():
    # Test with a simple menu dictionary
    menu = {
        "/overview": "Overview",
        "/sales": "Sales",
        "/products": "Products",
    }
    result = _build_and_validate_menu(menu)
    assert isinstance(result, NavMenu)
    assert all(isinstance(item, NavMenuItemLink) for item in result.items)

    # Test with absolute href
    menu = {"https://marimo.io": "marimo"}
    result = _build_and_validate_menu(menu)
    assert isinstance(result, NavMenu)

    # Test with a nested menu dictionary
    menu: dict[str, dict[str, str]] = {
        "Overview": {"/overview": "Overview", "/overview/summary": "Summary"},
        "Sales": {"/sales": "Sales", "/sales/summary": "Summary"},
        "Products": {"/products": "Products", "/products/summary": "Summary"},
    }
    result = _build_and_validate_menu(menu)
    assert isinstance(result, NavMenu)
    assert all(isinstance(item, NavMenuItemGroup) for item in result.items)

    # Test with invalid href
    menu = {"overview": "Overview"}
    with pytest.raises(ValueError):
        _build_and_validate_menu(menu)

    # Test with invalid menu item
    menu = {"/overview": 123}
    with pytest.raises(ValueError):
        _build_and_validate_menu(menu)

    # Test with missing label in submenu item
    menu = {"/overview": {"description": "Overview"}}
    with pytest.raises(ValueError):
        _build_and_validate_menu(menu)

    # Test with non-string description in submenu item
    menu = {"/overview": {"label": "Overview", "description": 123}}
    with pytest.raises(ValueError):
        _build_and_validate_menu(menu)
