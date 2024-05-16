# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Literal, Optional, Union, cast

from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType, build_stateless_plugin


@mddoc
def nav_menu(
    menu: dict[str, JSONType],
    *,
    orientation: Literal["horizontal", "vertical"] = "horizontal",
) -> Html:
    """
    Navigation menu component.

    This is useful for creating a navigation menu with hyperlinks,
    most used when creating multi-page applications, with
    `marimo.create_asgi_app` ([docs](https://docs.marimo.io/guides/deploying/programmatically.html)).

    **Examples.**

    ```python
    nav_menu = mo.nav_menu(
        {
            "/overview": "Overview",
            "/sales": f"{mo.icon('lucide:shopping-cart')} Sales",
            "/products": f"{mo.icon('lucide:package')} Products",
        }
    )
    ```

    # You can also nest dictionaries to create submenus
    ```python
    nav_menu = mo.nav_menu(
        {
            "/overview": "Overview",
            "Sales": {
                "/sales": "Overview",
                "/sales/invoices": {
                    "label": "Invoices",
                    "description": "View invoices",
                },
                "/sales/customers": {
                    "label": "Customers",
                    "description": "View customers",
                },
            },
        }
    )
    ```

    **Args.**

    - `menu`: a dictionary of tab names to tab content;
        the content can also be nested dictionaries (one level deep)
        strings are interpreted as markdown

    **Returns.**

    - An `Html` object.
    """

    menu_items = _build_and_validate_menu(menu)

    return Html(
        build_stateless_plugin(
            component_name="marimo-nav-menu",
            args={
                "items": asdict(menu_items)["items"],
                "orientation": orientation,
            },
        )
    )


@dataclass
class NavMenu:
    items: List[Union[NavMenuItemLink, NavMenuItemGroup]]


@dataclass
class NavMenuItemLink:
    label: str
    href: str
    description: Optional[str] = None


@dataclass
class NavMenuItemGroup:
    label: str
    items: List[NavMenuItemLink]


def _build_and_validate_menu(menu: dict[str, JSONType]) -> NavMenu:
    def validate_href(href: str) -> str:
        if not isinstance(href, str):
            raise ValueError(f"Invalid href: {href}, expected string")
        if (
            href.startswith("/")
            or href.startswith("#")
            or href.startswith("http")
        ):
            return href
        raise ValueError(f"Invalid href: {href}, must start with / or #")

    items: List[Union[NavMenuItemLink, NavMenuItemGroup]] = []
    for k, v in menu.items():
        if isinstance(v, str):
            items.append(
                NavMenuItemLink(label=md(v).text, href=validate_href(k))
            )
        elif isinstance(v, dict):
            subitems: List[NavMenuItemLink] = []
            for kk, vv in v.items():
                if isinstance(vv, str):
                    subitems.append(
                        NavMenuItemLink(
                            label=md(vv).text, href=validate_href(kk)
                        )
                    )
                elif isinstance(vv, dict):
                    label = vv.get("label")
                    description = vv.get("description", None)
                    if not label or not isinstance(label, str):
                        raise ValueError(
                            f"Invalid submenu item: {vv}, missing label"
                        )
                    if description and not isinstance(description, str):
                        raise ValueError(
                            f"Invalid submenu item: {vv}, expected"
                            " string for description"
                        )
                    subitems.append(
                        NavMenuItemLink(
                            label=md(label).text,
                            href=validate_href(kk),
                            description=(
                                md(cast(str, description)).text
                                if description
                                else None
                            ),
                        )
                    )
                else:
                    raise ValueError(
                        f"Invalid submenu item: {vv}, expected string, or dict"
                    )
            items.append(NavMenuItemGroup(label=md(k).text, items=subitems))
        else:
            raise ValueError(
                f"Invalid menu item: {v}, expected string or dict"
            )
    return NavMenu(items=items)
