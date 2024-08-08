# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import os
import traceback
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from marimo import _loggers
from marimo._data.series import (
    DataFrameSeries,
    get_category_series_info,
    get_date_series_info,
    get_number_series_info,
)
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import S as JSONTypeBound, UIElement
from marimo._runtime.functions import Function
from marimo._server.files.os_file_system import OSFileSystem
from marimo._server.models.files import FileInfo

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]


@mddoc
class number(UIElement[Optional[Numeric], Optional[Numeric]]):
    """
    A number picker over an interval.

    **Example.**

    ```python
    number = mo.ui.number(start=1, stop=10, step=2)
    ```

    Or from a dataframe series:

    ```python
    number = mo.ui.number.from_series(df["column_name"])
    ```

    **Attributes.**

    - `value`: the value of the number, possibly `None`
    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the number increment

    **Initialization Args.**

    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the number increment
    - `value`: default value
    - `debounce`: whether to debounce (rate-limit) value
        updates from the frontend
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _name: Final[str] = "marimo-number"

    def __init__(
        self,
        start: float,
        stop: float,
        step: Optional[float] = None,
        value: Optional[float] = None,
        debounce: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[Optional[Numeric]], None]] = None,
        full_width: bool = False,
    ) -> None:
        value = start if value is None else value
        if stop < start:
            raise ValueError(
                f"Invalid bounds: stop value ({stop}) must be greater than "
                f"start value ({start})"
            )
        elif value < start or value > stop:
            raise ValueError(
                f"Value out of bounds: The default value ({value}) must be "
                f"greater than start ({start}) and less than stop ({stop})."
            )

        # Lower bound
        self.start = start
        # Upper bound
        self.stop = stop
        # Increment size
        self.step = step
        super().__init__(
            component_name=number._name,
            initial_value=value,
            label=label,
            args={
                "start": start,
                "stop": stop,
                "step": step if step is not None else None,
                "debounce": debounce,
                "full-width": full_width,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "number":
        """Create a number picker from a dataframe series."""
        info = get_number_series_info(series)
        return number(
            start=info.min, stop=info.max, label=info.label, **kwargs
        )

    def _convert_value(self, value: Optional[Numeric]) -> Optional[Numeric]:
        """Value is `None` if user uses keyboard to delete contents of input"""
        return value


@mddoc
class slider(UIElement[Numeric, Numeric]):
    """
    A numeric slider over an interval.

    **Example.**

    ```python
    slider = mo.ui.slider(start=1, stop=10, step=2)
    ```

    Or from a dataframe series:

    ```python
    slider = mo.ui.slider.from_series(df["column_name"])
    ```

    **Attributes.**

    - `value`: the current numeric value of the slider
    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the slider increment
    - `steps`: list of steps

    **Initialization Args.**

    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the slider increment
    - `value`: default value
    - `debounce`: whether to debounce the slider to only send
        the value on mouse-up or drag-end
    - `orientation`: the orientation of the slider,
        either "horizontal" or "vertical"
    - `show_value`: whether to display the current value of the slider
    - `steps`: list of steps to customize the slider, mutually exclusive
        with `start`, `stop`, and `step`
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _name: Final[str] = "marimo-slider"
    _mapping: Optional[Dict[int, Numeric]] = None

    def __init__(
        self,
        start: Optional[Numeric] = None,
        stop: Optional[Numeric] = None,
        step: Optional[Numeric] = None,
        value: Optional[Numeric] = None,
        debounce: bool = False,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        show_value: bool = False,
        steps: Optional[Sequence[Numeric]] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[Optional[Numeric]], None]] = None,
        full_width: bool = False,
    ) -> None:
        self.start: Numeric
        self.stop: Numeric
        self.step: Optional[Numeric]
        self.steps: Optional[Sequence[Numeric]]

        # Guard against conflicting arguments
        if steps is not None and (
            start is not None or stop is not None or step is not None
        ):
            raise ValueError(
                "Invalid arguments: `steps` is mutually exclusive with "
                "`start`, `stop`, and `step`."
            )
        if steps is None and (start is None or stop is None):
            raise ValueError(
                "Missing arguments: `steps` xor both `start`"
                "and `stop` must be provided."
            )
        # If steps are provided
        if steps is not None:
            self._dtype = _infer_dtype(steps)
            self._mapping = dict(enumerate(steps))
            try:
                # check if steps is a sequence of numbers
                assert all(isinstance(num, (int, float)) for num in steps)
                assert len(steps) > 0
                value = steps[0] if value is None else value
                value = steps.index(value)
            except ValueError:
                print(
                    "Value out of bounds: default value should be in the steps"
                    ", set to first value."
                )
                value = 0
            except AssertionError as e:
                raise TypeError(
                    "Invalid steps: steps must be a sequence of numbers."
                ) from e

            # minimum value of interval
            self.start = steps[0]
            # maximum value of interval
            self.stop = steps[-1]
            # slider increment
            self.step = None
            # list of steps
            self.steps = steps

            super().__init__(
                component_name=slider._name,
                initial_value=value,
                label=label,
                args={
                    "start": 0,
                    "stop": len(steps) - 1,
                    "step": 1,
                    "steps": steps,
                    "debounce": debounce,
                    "orientation": orientation,
                    "show-value": show_value,
                    "full-width": full_width,
                },
                on_change=on_change,
            )
        else:
            assert start is not None
            assert stop is not None

            self._dtype = _infer_dtype([start, stop, step, value])
            value = start if value is None else value

            if stop < start:
                raise ValueError(
                    f"Invalid bounds: stop value ({stop}) "
                    "must be greater than "
                    f"start value ({start})"
                )
            if value < start or value > stop:
                raise ValueError(
                    f"Value out of bounds: default value ({value}) must be "
                    f"greater than start ({start}) "
                    f"and less than stop ({stop})."
                )

            self.start = start
            self.stop = stop
            self.step = step
            self.steps = None

            super().__init__(
                component_name=slider._name,
                initial_value=value,
                label=label,
                args={
                    "start": start,
                    "stop": stop,
                    "step": step if step is not None else None,
                    "steps": [],
                    "debounce": debounce,
                    "orientation": orientation,
                    "show-value": show_value,
                    "full-width": full_width,
                },
                on_change=on_change,
            )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "slider":
        """Create a slider from a dataframe series."""
        info = get_number_series_info(series)
        return slider(
            start=info.min, stop=info.max, label=info.label, **kwargs
        )

    def _convert_value(self, value: Numeric) -> Numeric:
        if self._mapping is not None:
            return cast(Numeric, self._dtype(self._mapping[int(value)]))
        return cast(Numeric, self._dtype(value))


@mddoc
class range_slider(UIElement[List[Numeric], Sequence[Numeric]]):
    """
    A numeric slider for specifying a range over an interval.

    **Example.**

    ```python
    range_slider = mo.ui.range_slider(start=1, stop=10, step=2, value=[2, 6])
    ```

    Or from a dataframe series:

    ```python
    range_slider = mo.ui.range_slider.from_series(df["column_name"])
    ```

    **Attributes.**

    - `value`: the current range value of the slider
    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the slider increment
    - `steps`: list of steps

    **Initialization Args.**

    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the slider increment
    - `value`: default value
    - `debounce`: whether to debounce the slider to only send
        the value on mouse-up or drag-end
    - `orientation`: the orientation of the slider,
        either "horizontal" or "vertical"
    - `show_value`: whether to display the current value of the slider
    - `steps`: list of steps to customize the slider, mutually exclusive
        with `start`, `stop`, and `step`
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _name: Final[str] = "marimo-range-slider"
    _mapping: Optional[dict[int, Numeric]] = None

    def __init__(
        self,
        start: Optional[Numeric] = None,
        stop: Optional[Numeric] = None,
        step: Optional[Numeric] = None,
        value: Optional[Sequence[Numeric]] = None,
        debounce: bool = False,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        show_value: bool = False,
        steps: Optional[Sequence[Numeric]] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[Sequence[Numeric]], None]] = None,
        full_width: bool = False,
    ) -> None:
        self.start: Numeric
        self.stop: Numeric
        self.step: Optional[Numeric]
        self.steps: Optional[Sequence[Numeric]]

        if steps is not None and (
            start is not None or stop is not None or step is not None
        ):
            raise ValueError(
                "Invalid arguments: `steps` is mutually exclusive with "
                "`start`, `stop`, and `step`."
            )
        if steps is None and (start is None or stop is None):
            raise ValueError(
                "Missing arguments: `steps` xor both `start`"
                "and `stop` must be provided."
            )

        if steps is not None:
            self._dtype = _infer_dtype(steps)
            self._mapping = dict(enumerate(steps))

            try:
                assert all(isinstance(num, (int, float)) for num in steps)
                assert len(steps) > 0
                value = [steps[0], steps[-1]] if value is None else value
                value = [steps.index(num) for num in value]
            except ValueError:
                print(
                    "Value out of bounds: default value should be in the"
                    "steps, set to first and last values."
                )
                value = [0, len(steps) - 1]
            except AssertionError as e:
                raise TypeError(
                    "Invalid steps: steps must be a sequence of numbers."
                ) from e

            # minimum value of interval
            self.start = steps[0]
            # maximum value of interval
            self.stop = steps[-1]
            # slider increment
            self.step = None
            # list of steps
            self.steps = steps

            super().__init__(
                component_name=range_slider._name,
                initial_value=list(value),
                label=label,
                args={
                    "start": 0,
                    "stop": len(steps) - 1,
                    "step": 1,
                    "steps": steps,
                    "debounce": debounce,
                    "orientation": orientation,
                    "show-value": show_value,
                    "full-width": full_width,
                },
                on_change=on_change,
            )
        else:
            assert start is not None
            assert stop is not None

            self._dtype = _infer_dtype([start, stop, step, value])

            value = [start, stop] if value is None else value

            if stop < start or value[1] < value[0]:
                raise ValueError(
                    "Invalid bounds: stop value must be "
                    "greater than start value."
                )
            if value[0] < start or value[1] > stop:
                raise ValueError(
                    f"Value out of bounds: default value ({value}) must be "
                    f"a range within start ({start}) and stop ({stop})."
                )

            self.start = start
            self.stop = stop
            self.step = step
            self.steps = None

            super().__init__(
                component_name=range_slider._name,
                initial_value=list(value),
                label=label,
                args={
                    "start": start,
                    "stop": stop,
                    "step": step if step is not None else None,
                    "steps": [],
                    "debounce": debounce,
                    "orientation": orientation,
                    "show-value": show_value,
                    "full-width": full_width,
                },
                on_change=on_change,
            )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "range_slider":
        """Create a range slider from a dataframe series."""
        info = get_number_series_info(series)
        return range_slider(
            start=info.min, stop=info.max, label=info.label, **kwargs
        )

    def _convert_value(self, value: List[Numeric]) -> Sequence[Numeric]:
        if self._mapping is not None:
            return cast(
                Sequence[Numeric],
                [self._dtype(self._mapping[int(v)]) for v in value],
            )
        return cast(Sequence[Numeric], [self._dtype(v) for v in value])


def _infer_dtype(
    items: Sequence[Union[Numeric, Sequence[Numeric], None]],
) -> type[int] | type[float]:
    """Infer the dtype of a sequence of numbers."""
    for item in items:
        if isinstance(item, Sequence):
            if any(isinstance(subitem, float) for subitem in item):
                return float
        if any(isinstance(item, float) for item in items):
            return float
    return int


@mddoc
class checkbox(UIElement[bool, bool]):
    """
    A boolean checkbox.

    **Example.**

    ```python
    checkbox = mo.ui.checkbox()
    ```

    **Attributes.**

    - `value`: a boolean, `True` if checked

    **Initialization Args.**

    - `value`: default value, True or False
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-checkbox"

    def __init__(
        self,
        value: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__(
            component_name=checkbox._name,
            initial_value=value,
            label=label,
            args={},
            on_change=on_change,
        )

    def _convert_value(self, value: bool) -> bool:
        return value


@mddoc
class radio(UIElement[Optional[str], Any]):
    """
    A radio group.

    **Example.**

    ```python
    radiogroup = mo.ui.radio(
        options=["a", "b", "c"], value="a", label="choose one"
    )
    ```

    ```python
    radiogroup = mo.ui.radio(
        options={"one": 1, "two": 2, "three": 3},
        value="one",
        label="pick a number",
    )
    ```

    Or from a dataframe series:

    ```python
    radiogroup = mo.ui.radio.from_series(df["column_name"])
    ```

    **Attributes.**

    - `value`: the value of the selected radio option
    - `options`: a dict mapping option name to option value

    **Initialization Args.**

    - `options`: sequence of text options, or dict mapping option name
                 to option value
    - `value`: default option name, if None, starts with nothing checked
    - `label`: optional text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-radio"

    def __init__(
        self,
        options: Sequence[str] | dict[str, Any],
        value: Optional[str] = None,
        inline: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[Any], None]] = None,
    ) -> None:
        if not isinstance(options, dict):
            if len(set(options)) != len(options):
                raise ValueError("A radio group cannot have repeated options.")
            options = {option: option for option in options}
        self.options = options
        super().__init__(
            component_name=radio._name,
            initial_value=value,
            label=label,
            args={
                "options": list(options.keys()),
                "inline": inline,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "radio":
        """Create a radio group from a dataframe series."""
        info = get_category_series_info(series)
        return radio(
            options=info.categories,
            label=info.label,
            **kwargs,
        )

    def _convert_value(self, value: Optional[str]) -> Any:
        return self.options[value] if value is not None else None


@mddoc
class text(UIElement[str, str]):
    """
    A text input.

    **Example.**

    ```python
    text = mo.ui.text(value="Hello, World!")
    ```

    **Attributes.**

    - `value`: a string of the input's contents

    **Initialization Args.**

    - `value`: default value of text box
    - `placeholder`: placeholder text to display when the text area is empty
    - `kind`: input kind, one of `"text"`, `"password"`, `"email"`, or `"url"`
        defaults to `"text"`
    - `max_length`: maximum length of input
    - `disabled`: whether the input is disabled
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _name: Final[str] = "marimo-text"

    def __init__(
        self,
        value: str = "",
        placeholder: str = "",
        kind: Literal["text", "password", "email", "url"] = "text",
        max_length: Optional[int] = None,
        disabled: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[str], None]] = None,
        full_width: bool = False,
    ) -> None:
        super().__init__(
            component_name=text._name,
            initial_value=value,
            label=label,
            args={
                "placeholder": placeholder,
                "kind": kind,
                "max-length": max_length,
                "full-width": full_width,
                "disabled": disabled,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: str) -> str:
        return value


@mddoc
class text_area(UIElement[str, str]):
    """
    A text area that is larger than `ui.text`.

    **Example.**

    ```python
    text_area = mo.ui.text_area()
    ```

    **Attributes.**

    - `value`: a string of the text area contents

    **Initialization Args.**

    - `value`: initial value of the text area
    - `placeholder`: placeholder text to display when the text area is empty
    - `max_length`: maximum length of input
    - `disabled`: whether the input is disabled
    - `rows`: number of rows of text to display
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _name: Final[str] = "marimo-text-area"

    def __init__(
        self,
        value: str = "",
        placeholder: str = "",
        max_length: Optional[int] = None,
        disabled: bool = False,
        rows: Optional[int] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[str], None]] = None,
        full_width: bool = False,
    ) -> None:
        super().__init__(
            component_name=text_area._name,
            initial_value=value,
            label=label,
            args={
                "placeholder": placeholder,
                "max-length": max_length,
                "disabled": disabled,
                "full-width": full_width,
                "rows": rows,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: str) -> str:
        return value


@mddoc
class code_editor(UIElement[str, str]):
    """
    A code editor.

    **Example.**

    ```python
    code_editor = mo.ui.code_editor()
    ```

    **Attributes.**

    - `value`: a string of the code editor contents

    **Initialization Args.**

    - `value`: initial value of the code editor
    - `language`: language of the code editor, defaults to `"python"`; most
        major languages are supported, including "sql", "javascript",
        "typescript", "html", "css", "c", "cpp", "rust", and more
    - `placeholder`: placeholder text to display when the code editor is empty
    - `theme`: theme of the code editor, defaults to the editor's default
    - `disabled`: whether the input is disabled
    - `min_height`: minimum height of the code editor in pixels
    - `max_height`: maximum height of the code editor in pixels
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-code-editor"

    def __init__(
        self,
        value: str = "",
        language: str = "python",
        placeholder: str = "",
        theme: Optional[Literal["light", "dark"]] = None,
        disabled: bool = False,
        min_height: Optional[int] = None,
        max_height: Optional[int] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        if (
            min_height is not None
            and max_height is not None
            and min_height > max_height
        ):
            raise ValueError(
                f"min_height ({min_height}) must be <= max_height {max_height}"
            )

        super().__init__(
            component_name=code_editor._name,
            initial_value=value,
            label=label,
            args={
                "language": language,
                "placeholder": placeholder,
                "theme": theme,
                "disabled": disabled,
                "min-height": min_height,
                "max-height": max_height,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: str) -> str:
        return value


@mddoc
class dropdown(UIElement[List[str], Any]):
    """
    A dropdown menu.

    **Example.**

    ```python
    dropdown = mo.ui.dropdown(
        options=["a", "b", "c"], value="a", label="choose one"
    )
    ```

    ```python
    dropdown = mo.ui.dropdown(
        options={"one": 1, "two": 2, "three": 3},
        value="one",
        label="pick a number",
    )
    ```

    Or from a dataframe series:

    ```python
    dropdown = mo.ui.dropdown.from_series(df["column_name"])
    ```

    **Attributes.**

    - `value`: the selected value, or `None` if no selection
    - `options`: a dict mapping option name to option value
    - `selected_key`: the selected option's key, or `None` if no selection

    **Initialization Args.**

    - `options`: sequence of text options, or dict mapping option name
                 to option value
    - `value`: default option name
    - `allow_select_none`: whether to include special option (`"--"`) for a
                           `None` value; when `None`, defaults to `True` when
                           `value` is `None`
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _MAX_OPTIONS: Final[int] = 1000
    _name: Final[str] = "marimo-dropdown"
    _selected_key: Optional[str] = None

    def __init__(
        self,
        options: Sequence[str] | dict[str, Any],
        value: Optional[str] = None,
        allow_select_none: Optional[bool] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[Any], None]] = None,
        full_width: bool = False,
    ) -> None:
        if len(options) > dropdown._MAX_OPTIONS:
            raise ValueError(
                "The maximum number of dropdown options allowed "
                f"is {dropdown._MAX_OPTIONS}, but your dropdown has "
                f"{len(options)} options. "
                "If you really want to expose that many options, consider "
                "using `mo.ui.text()` to let the user type an option name, "
                "and `mo.ui.table()` to present the options matching the "
                "user's query.",
            )

        if not isinstance(options, dict):
            options = {option: option for option in options}

        if "--" in options:
            raise ValueError(
                "The option name '--' is reserved by marimo"
                "; please use another name."
            )

        self.options = options
        initial_value = [value] if value is not None else []
        if allow_select_none is None:
            allow_select_none = value is None
        elif not allow_select_none and value is None:
            raise ValueError(
                "when `allow_select_none` is False, a non-None default value "
                "must be provided."
            )

        super().__init__(
            component_name=dropdown._name,
            initial_value=initial_value,
            label=label,
            args={
                "options": list(self.options.keys()),
                "allow-select-none": allow_select_none,
                "full-width": full_width,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "dropdown":
        """Create a dropdown from a dataframe series."""
        info = get_category_series_info(series)
        return dropdown(
            options=info.categories,
            label=info.label,
            **kwargs,
        )

    def _convert_value(self, value: list[str]) -> Any:
        if value:
            assert len(value) == 1
            self._selected_key = value[0]
            return self.options[value[0]]
        else:
            self._selected_key = None
            return None

    @property
    def selected_key(self) -> Optional[str]:
        """The selected option's key, or `None` if no selection."""
        return self._selected_key


@mddoc
class multiselect(UIElement[List[str], List[object]]):
    """
    A multiselect input.

    **Example.**

    ```python
    multiselect = mo.ui.multiselect(
        options=["a", "b", "c"], label="choose some options"
    )
    ```

    Or from a dataframe series:

    ```python
    multiselect = mo.ui.multiselect.from_series(df["column_name"])
    ```

    **Attributes.**

    - `value`: the selected values, or `None` if no selection
    - `options`: a dict mapping option name to option value

    **Initialization Args.**

    - `options`: sequence of text options, or dict mapping option name
                 to option value
    - `value`: a list of initially selected options
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    - `max_selections`: maximum number of items that can be selected
    """

    _MAX_OPTIONS: Final[int] = 100000
    _name: Final[str] = "marimo-multiselect"

    def __init__(
        self,
        options: Sequence[str] | dict[str, Any],
        value: Optional[Sequence[str]] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[List[object]], None]] = None,
        full_width: bool = False,
        max_selections: Optional[int] = None,
    ) -> None:
        if len(options) > multiselect._MAX_OPTIONS:
            raise ValueError(
                "The maximum number of options allowed "
                f"is {multiselect._MAX_OPTIONS}, but your multiselect has "
                f"{len(options)} options. "
                "If you really want to expose that many options, consider "
                "using `mo.ui.text()` to let the user type an option name, "
                "and `mo.ui.table()` to present the options matching the "
                "user's query.",
            )

        if not isinstance(options, dict):
            options = {option: option for option in options}

        self.options = options
        initial_value = list(value) if value is not None else []

        if max_selections is not None:
            if max_selections < 0:
                raise ValueError("max_selections cannot be less than 0.")
            if max_selections < len(initial_value):
                raise ValueError(
                    "Initial value cannot be greater than max_selections."
                )

        super().__init__(
            component_name=multiselect._name,
            initial_value=initial_value,
            label=label,
            args={
                "options": list(self.options.keys()),
                "full-width": full_width,
                "max-selections": max_selections,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "multiselect":
        """Create a multiselect from a dataframe series."""
        info = get_category_series_info(series)
        return multiselect(
            options=info.categories,
            label=info.label,
            **kwargs,
        )

    def _convert_value(self, value: list[str]) -> list[object]:
        return [self.options[v] for v in value]


@mddoc
class button(UIElement[Any, Any]):
    """
    A button with an optional callback and optional value.

    **Example.**

    ```python
    # a button that when clicked will execute
    # any cells referencing that button
    button = mo.ui.button()
    ```

    ```python
    # a counter implementation
    counter_button = mo.ui.button(
        value=0, on_click=lambda value: value + 1, label="increment"
    )

    # adding intent
    delete_button = mo.ui.button(
        label="Do not click",
        kind="danger",
    )
    ```

    **Attributes.**

    - `value`: the value of the button

    **Initialization Args.**

    - `on_click`: a callable called on click that takes the current
       value of the button and returns a new value
    - `value`: an initial value for the button
    - `kind`: 'neutral', 'success', 'warn', or 'danger'
    - `disabled`: whether the button is disabled
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _name: Final[str] = "marimo-button"

    def __init__(
        self,
        on_click: Optional[Callable[[Any], Any]] = None,
        value: Optional[Any] = None,
        kind: Literal["neutral", "success", "warn", "danger"] = "neutral",
        disabled: bool = False,
        tooltip: Optional[str] = None,
        *,
        label: str = "click here",
        on_change: Optional[Callable[[Any], None]] = None,
        full_width: bool = False,
    ) -> None:
        self._on_click = (lambda _: value) if on_click is None else on_click
        self._initial_value = value
        # This should be kept in sync with mo.ui.run_button()
        super().__init__(
            component_name=button._name,
            # frontend's value is always a counter
            initial_value=0,
            label=label,
            args={
                "kind": kind,
                "disabled": disabled,
                "tooltip": tooltip,
                "full-width": full_width,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: Any) -> Any:
        if value == 0:
            # frontend's value == 0 only during initialization; first value
            # frontend will send is 1
            return self._initial_value
        try:
            return self._on_click(self._value)
        except Exception:
            LOGGER.error(
                "on_click handler for button (%s) raised an Exception:\n %s ",
                str(self),
                traceback.format_exc(),
            )
            return None


@dataclass
class FileUploadResults:
    """A file's name and its contents."""

    name: str
    contents: bytes

    def __repr__(self) -> str:
        # Truncate contents because it can be very long
        return f"FileUploadResults(name='{self.name}', contents=...)"


@mddoc
class file(UIElement[List[Tuple[str, str]], Sequence[FileUploadResults]]):
    """
    A button or drag-and-drop area to upload a file.

    Once a file is uploaded, the UI element's value is a list of
    `namedtuples (name, contents)`, where `name` is the filename and
    `contents` is the contents of the file. Alternatively, use the methods
    `name(index: int = 0)` and `contents(index: int = 0)` to retrieve the
    name or contents of the file at a specified index.

    Use the `kind` argument to switch between a button and a drag-and-drop
    area.

    The maximum file size is 100MB.

    **Examples.**

    Uploading a single file:

    ```python
    f = mo.ui.file()

    # access the uploaded file's name
    f.value[0].name
    # or
    f.name()

    # access the uploaded file's contents
    f.value[0].contents
    # or
    f.contents()
    ```

    Uploading multiple files, accepting only .png and .jpg extensions:

    ```python
    f = mo.ui.file(filetypes=[".png", ".jpg"], multiple=True)

    # access an uploaded file's name
    f.value[index].name
    # or
    f.name(index)

    # access the uploaded file's contents
    f.value[index].contents
    # or
    f.contents(index)
    ```

    **Attributes.**

    - `value`: a sequence of `FileUploadResults`, which have string `name` and
               `bytes` `contents` fields

    **Methods.**

    - `name(self, index: int = 0) -> Optional[str]`: Get the name of the
      uploaded file at `index`.
    - `contents(self, index: int = 0) -> Optional[bytes]`: Get the contents of
      the uploaded file at `index`.

    **Initialization Args.**

    - `filetypes`: the file types accepted; for example,
       `filetypes=[".png", ".jpg"]`. If `None`, all files are accepted.
       In addition to extensions, you may provide `"audio/*"`, `"video/*"`,
       or `"image/*"` to accept any audio, video, or image file.
    - `multiple`: if True, allow the user to upload multiple files
    - `kind`: `"button"` or `"area"`
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-file"

    def __init__(
        self,
        filetypes: Optional[Sequence[str]] = None,
        multiple: bool = False,
        kind: Literal["button", "area"] = "button",
        *,
        label: str = "",
        on_change: Optional[
            Callable[[Sequence[FileUploadResults]], None]
        ] = None,
    ) -> None:
        super().__init__(
            component_name=file._name,
            initial_value=[],
            label=label,
            args={
                "filetypes": filetypes if filetypes is not None else [],
                "multiple": multiple,
                "kind": kind,
            },
            on_change=on_change,
        )

    def _convert_value(
        self, value: list[tuple[str, str]]
    ) -> Sequence[FileUploadResults]:
        return tuple(
            FileUploadResults(name=e[0], contents=base64.b64decode(e[1]))
            for e in value
        )

    def name(self, index: int = 0) -> Optional[str]:
        """Get file name at index."""
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].name

    def contents(self, index: int = 0) -> Optional[bytes]:
        """Get file contents at index."""
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].contents


@dataclass
class ListDirectoryArgs:
    path: str


@dataclass
class ListDirectoryResponse:
    files: List[FileInfo]


@mddoc
class file_browser(UIElement[List[Dict[str, Any]], Sequence[FileInfo]]):
    """
    File browser for browsing and selecting server-side files.

    **Examples.**

    Selecting multiple files:

    ```python
    file_browser = mo.ui.file_browser(
        initial_path="path/to/dir", multiple=True
    )

    # Access the selected file path(s):
    file_browser.path(index)

    # Get name of selected file(s)
    file_browser.name(index)
    ```

    **Attributes.**

    - `value`: a sequence of file paths representing selected files.

    **Initialization Args.**

    - `initial_path`: starting directory, default current working directory.
    - `filetypes`: the file types to display in each directory; for example,
       `filetypes=[".txt", ".csv"]`. If `None`, all files are displayed.
    - `selection_mode`: either "file" or "directory".
    - `multiple`: if True, allow the user to select multiple files.
    - `restrict_navigation`: if True, prevent the user from navigating
       any level above the given path.
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-file-browser"

    def __init__(
        self,
        initial_path: str = "",
        filetypes: Optional[Sequence[str]] = None,
        selection_mode: str = "file",
        multiple: bool = True,
        restrict_navigation: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[Sequence[FileInfo]], None]] = None,
    ) -> None:
        self.filetypes = filetypes

        if (
            selection_mode != "file"
            and selection_mode != "directory"
            and selection_mode != "all"
        ):
            raise ValueError(
                "Invalid argument for selection_mode. "
                + "Must be either 'file' or 'directory'."
            )
        else:
            self.selection_mode = selection_mode

        if not initial_path:
            initial_path = os.getcwd()

        super().__init__(
            component_name=file_browser._name,
            initial_value=[],
            label=label,
            args={
                "initial-path": initial_path,
                "selection-mode": selection_mode,
                "filetypes": filetypes if filetypes is not None else [],
                "multiple": multiple,
                "restrict-navigation": restrict_navigation,
            },
            functions=(
                Function(
                    name=self.list_directory.__name__,
                    arg_cls=ListDirectoryArgs,
                    function=self.list_directory,
                ),
            ),
            on_change=on_change,
        )

    def list_directory(self, args: ListDirectoryArgs) -> ListDirectoryResponse:
        files = []
        files_in_path = OSFileSystem().list_files(args.path)

        for file in files_in_path:
            _, extension = os.path.splitext(file.name)

            if self.selection_mode == "directory" and not file.is_directory:
                continue

            if self.filetypes and not file.is_directory:
                if extension not in self.filetypes:
                    continue

            files.append(file)

        return ListDirectoryResponse(files)

    def _convert_value(
        self, value: list[Dict[str, Any]]
    ) -> Sequence[FileInfo]:
        return tuple(
            FileInfo(
                id=file["id"],
                name=file["name"],
                path=file["path"],
                is_directory=file["is_directory"],
                is_marimo_file=file["is_marimo_file"],
            )
            for file in value
        )

    def name(self, index: int = 0) -> Optional[str]:
        """Get file name at index."""
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].name

    def path(self, index: int = 0) -> Optional[str]:
        """Get file path at index."""
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].path


@mddoc
class date(UIElement[str, dt.date]):
    """
    A date picker with an optional start and stop date.

    **Example.**

    ```python
    # initialize the date picker at a given date
    date = mo.ui.date(value="2022-01-01")
    ```

    ```python
    # when value is omitted, date picker initializes with today's date
    date = mo.ui.date()
    ```

    ```python
    # create a date picker with bounds
    date = mo.ui.date(
        value="2022-06-01",
        start="2022-01-01",
        stop="2022-12-31",
    )
    ```

    Or from a dataframe series:

    ```python
    date = mo.ui.date.from_series(df["column_name"])
    ```

    **Attributes.**

    - `value`: a str (YYYY-MM-DD) or `datetime.date` object of the chosen date
    - `start`: the start date
    - `stop`: the stop date

    **Initialization Args.**

    - `start`: minimum date selectable; if None, defaults to 01-01-0001
    - `stop`: maximum date selectable; if None, defaults to 12-31-9999
    - `value`: default date
        - if `None` and `start` and `stop` are `None`, defaults to the
          current day;
        - else if `None` and `start` is not `None`, defaults to `start`;
        - else if `None` and `stop` is not `None`, defaults to `stop`
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
        container
    """

    _name: Final[str] = "marimo-date-picker"

    DATEFORMAT = "%Y-%m-%d"

    def __init__(
        self,
        start: Optional[dt.date | str] = None,
        stop: Optional[dt.date | str] = None,
        value: Optional[dt.date | str] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[dt.date], None]] = None,
        full_width: bool = False,
    ) -> None:
        if isinstance(start, str):
            start = self._convert_value(start)
        if isinstance(stop, str):
            stop = self._convert_value(stop)
        if isinstance(value, str):
            value = self._convert_value(value)

        if value is None:
            if start is None and stop is None:
                value = dt.date.today()
            elif start is not None:
                value = start
            else:
                value = stop
        value = cast(dt.date, value)

        self._start = dt.date(dt.MINYEAR, 1, 1) if start is None else start
        self._stop = dt.date(dt.MAXYEAR, 12, 31) if stop is None else stop

        if self._stop < self._start:
            raise ValueError(
                f"The stop date ({stop}) must be greater than "
                f"the start date ({start})"
            )
        elif value < self._start or value > self._stop:
            raise ValueError(
                f"The default value ({value}) must be greater than "
                f"the start date ({start}) and less than the stop "
                f"date ({stop})."
            )

        super().__init__(
            component_name=date._name,
            initial_value=value.isoformat(),
            label=label,
            args={
                "start": self._start.isoformat(),
                "stop": self._stop.isoformat(),
                "full-width": full_width,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "date":
        """Create a date picker from a dataframe series."""
        info = get_date_series_info(series)
        return date(
            start=info.min,
            stop=info.max,
            label=info.label,
            **kwargs,
        )

    def _convert_value(self, value: str) -> dt.date:
        return dt.datetime.strptime(value, self.DATEFORMAT).date()

    @property
    def start(self) -> dt.date:
        return self._start

    @property
    def stop(self) -> dt.date:
        return self._stop


T = TypeVar("T")


@dataclasses.dataclass
class ValueArgs:
    value: Optional[JSONType] = None


@mddoc
class form(UIElement[Optional[JSONTypeBound], Optional[T]]):
    """
    A submittable form linked to a UIElement.

    Use a `form` to prevent sending UI element values to Python until a button
    is clicked.

    The value of a `form` is the value of the underlying
    element the last time the form was submitted.

    **Example.**

    ```python
    # Create a form with chaining
    form = mo.ui.slider(1, 100).form()
    ```

    ```python
    # Create a form with multiple elements
    form = (
        mo.md('''
        **Your form.**

        {name}

        {date}
    ''')
        .batch(
            name=mo.ui.text(label="name"),
            date=mo.ui.date(label="date"),
        )
        .form(show_clear_button=True, bordered=False)
    )
    ```

    ```python
    # Instantiate a form directly
    form = mo.ui.form(element=mo.ui.slider(1, 100))
    ```

    **Attributes.**

    - `value`: the value of the wrapped element when the form's submit button
      was last clicked
    - `element`: a copy of the wrapped element

    **Initialization Args.**

    - `element`: the element to wrap
    - `bordered`: whether the form should have a border
    - `loading`: whether the form should be in a loading state
    - `submit_button_label`: the label of the submit button
    - `submit_button_tooltip`: the tooltip of the submit button
    - `submit_button_disabled`: whether the submit button should be disabled
    - `clear_on_submit`: whether the form should clear its contents after
        submitting
    - `show_clear_button`: whether the form should show a clear button
    - `clear_button_label`: the label of the clear button
    - `clear_button_tooltip`: the tooltip of the clear button
    - `validate`: a function that takes the form's value and returns an error
        message if the value is invalid, or `None` if the value is valid
    - `label`: text label for the form
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-form"

    def __init__(
        self,
        element: UIElement[JSONTypeBound, T],
        *,
        bordered: bool = True,
        loading: bool = False,
        submit_button_label: str = "Submit",
        submit_button_tooltip: Optional[str] = None,
        submit_button_disabled: bool = False,
        clear_on_submit: bool = False,
        show_clear_button: bool = False,
        clear_button_label: str = "Clear",
        clear_button_tooltip: Optional[str] = None,
        validate: Optional[
            Callable[[Optional[JSONType]], Optional[str]]
        ] = None,
        label: str = "",
        on_change: Optional[Callable[[Optional[T]], None]] = None,
    ) -> None:
        self.element = element._clone()
        self.validate = validate
        super().__init__(
            component_name=form._name,
            initial_value=None,
            label=label,
            args={
                "element-id": self.element._id,
                "loading": loading,
                "bordered": bordered,
                "submit-button-label": submit_button_label,
                "submit-button-tooltip": submit_button_tooltip,
                "submit-button-disabled": submit_button_disabled,
                "clear-on-submit": clear_on_submit,
                "show-clear-button": show_clear_button,
                "clear-button-label": clear_button_label,
                "clear-button-tooltip": clear_button_tooltip,
                "should-validate": validate is not None,
            },
            slotted_html=self.element.text,
            on_change=on_change,
            functions=(
                Function(
                    name="validate",
                    arg_cls=ValueArgs,
                    function=self._validate,
                ),
            ),
        )

    def _validate(self, value: ValueArgs) -> Optional[str]:
        if self.validate is None:
            return None
        return self.validate(value.value)

    def _convert_value(self, value: Optional[JSONTypeBound]) -> Optional[T]:
        if value is None:
            return None
        self.element._update(value)
        return self.element.value
