# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
import weakref
from dataclasses import dataclass
from typing import Any, Callable, Optional

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory


class IPythonFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "IPython"

    def register(self) -> Callable[[], None]:
        import IPython.display  # type:ignore

        from marimo._output import formatting
        from marimo._runtime.output import _output

        # Dictionary to store display objects by ID
        display_objects: weakref.WeakValueDictionary[str, Any] = (
            weakref.WeakValueDictionary()
        )

        def clear_display_objects() -> None:
            """Clear all stored display objects."""
            display_objects.clear()

        old_display = IPython.display.display
        old_update_display = getattr(IPython.display, "update_display", None)

        # DisplayHandle class to match IPython's API
        class DisplayHandle:
            def __init__(self, display_id: str):
                self.display_id = display_id

            def update(self, obj: Any, **kwargs: Any) -> None:
                update_display(obj, display_id=self.display_id, **kwargs)

        # Monkey patch IPython.display.display, which imperatively writes
        # outputs to the frontend
        @functools.wraps(old_display)
        def display(*objs: Any, **kwargs: Any) -> Optional[DisplayHandle]:
            # If clear is True, clear the output before displaying
            if kwargs.pop("clear", False):
                _output.clear()

            # Get display_id if provided
            display_id = kwargs.pop("display_id", None)
            if display_id is True:  # Generate a new display_id if True
                import uuid

                display_id = str(uuid.uuid4())

            raw = kwargs.pop("raw", False)
            for value in objs:
                # raw means it's a mimebundle, with the key (mime) and value (raw data)
                if raw and isinstance(value, dict):
                    output_value = ReprMimeBundle(value)
                else:
                    output_value = value

                # Store the object if display_id is provided
                if display_id is not None:
                    display_objects[display_id] = output_value
                    # Clean up old display objects if we have too many
                    if len(display_objects) > 1000:  # Arbitrary limit
                        clear_display_objects()

                _output.append(output_value)

            # Return a DisplayHandle if display_id is provided
            if display_id is not None:
                return DisplayHandle(display_id)
            return None

        # Implement update_display function
        def update_display(
            obj: Any, *, display_id: str, **kwargs: Any
        ) -> None:
            """Update an existing display by id

            Parameters
            ----------
            obj : Any
                The object with which to update the display
            display_id : str
                The id of the display to update
            """
            if display_id not in display_objects:
                return

            # Clear the output before updating
            # _output.clear()

            # Update the stored object
            raw = kwargs.pop("raw", False)
            if raw and isinstance(obj, dict):
                display_objects[display_id] = ReprMimeBundle(obj)
            else:
                display_objects[display_id] = obj

            # Append the updated object to the output
            _output.replace(display_objects[display_id])

        # Patch both display and update_display
        IPython.display.display = display
        IPython.display.update_display = update_display

        # Patching display_functions handles display_markdown, display_x, etc.
        try:
            IPython.core.display_functions.display = display  # type: ignore
            IPython.core.display_functions.update_display = update_display  # type: ignore
        except AttributeError:
            pass

        def unpatch() -> None:
            clear_display_objects()  # Clean up on unpatch
            IPython.display.display = old_display  # type: ignore
            if old_update_display is not None:
                IPython.display.update_display = old_update_display  # type: ignore
            else:
                delattr(IPython.display, "update_display")

            try:
                IPython.core.display_functions.display = old_display  # type: ignore
                if old_update_display is not None:
                    IPython.core.display_functions.update_display = (
                        old_update_display  # type: ignore
                    )
                else:
                    delattr(IPython.core.display_functions, "update_display")
            except AttributeError:
                pass

        @formatting.formatter(
            IPython.display.HTML  # type:ignore
        )
        def _format_html(
            html: IPython.display.HTML,  # type:ignore
        ) -> tuple[KnownMimeType, str]:
            if html.url is not None:
                # TODO(akshayka): resize iframe not working
                data = h.iframe(
                    src=html.url,
                    onload="__resizeIframe(this)",
                    width="100%",
                )
            else:
                data = str(html._repr_html_())  # type: ignore

            return ("text/html", data)

        return unpatch


@dataclass
class ReprMimeBundle:
    data: dict[str, Any]

    def _repr_mimebundle_(
        self,
        include: Any = None,
        exclude: Any = None,
    ) -> dict[str, Any]:
        del include, exclude
        return self.data
