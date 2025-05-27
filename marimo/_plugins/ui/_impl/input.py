# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import dataclasses
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Final,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
)

from marimo import _loggers
from marimo._data.series import (
    DataFrameSeries,
    get_category_series_info,
    get_number_series_info,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import S as JSONTypeBound, UIElement
from marimo._plugins.validators import (
    validate_between_range,
    validate_range,
    warn_js_safe_number,
)
from marimo._runtime.functions import Function

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]


@mddoc
class number(UIElement[Optional[Numeric], Optional[Numeric]]):
    """
    A number picker over an interval.

    Example:
        ```python
        number = mo.ui.number(start=1, stop=10, step=2)
        ```

        Or for integer-only values:

        ```python
        number = mo.ui.number(step=1)
        ```

        Or from a dataframe series:

        ```python
        number = mo.ui.number.from_series(df["column_name"])
        ```

    Attributes:
        value (Optional[Numeric]): The value of the number, possibly `None`.
        start (Optional[float]): The minimum value of the interval.
        stop (Optional[float]): The maximum value of the interval.
        step (Optional[float]): The number increment.

    Args:
        start (Optional[float]): The minimum value of the interval. Defaults to None.
        stop (Optional[float]): The maximum value of the interval. Defaults to None.
        step (Optional[float]): The number increment. Defaults to None.
        value (Optional[float]): The default value. Defaults to None.
        debounce (bool): Whether to debounce (rate-limit) value updates from the frontend. Defaults to False.
        label (str): Markdown label for the element. Defaults to an empty string.
        on_change (Optional[Callable[[Optional[Numeric]], None]]): Optional callback to run when this element's value changes. Defaults to None.
        full_width (bool): Whether the input should take up the full width of its container. Defaults to False.
        disabled (bool, optional): Whether the input is disabled. Defaults to False.

    Methods:
        from_series(series: DataFrameSeries, **kwargs: Any) -> number:
            Create a number picker from a dataframe series.
    """

    _name: Final[str] = "marimo-number"

    def __init__(
        self,
        start: Optional[float] = None,
        stop: Optional[float] = None,
        step: Optional[float] = None,
        value: Optional[float] = None,
        debounce: bool = False,
        *,
        label: str = "",
        on_change: Optional[Callable[[Optional[Numeric]], None]] = None,
        full_width: bool = False,
        disabled: bool = False,
    ) -> None:
        validate_range(min_value=start, max_value=stop)
        validate_between_range(value, min_value=start, max_value=stop)
        warn_js_safe_number(start, stop, value)

        # Set value to min or max if None
        if value is None:
            if start is not None:
                value = start
            elif stop is not None:
                value = stop

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
                "disabled": disabled,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> number:
        """Create a number picker from a dataframe series."""
        info = get_number_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return number(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(self, value: Optional[Numeric]) -> Optional[Numeric]:
        """Value is `None` if user uses keyboard to delete contents of input"""
        return value


@mddoc
class slider(UIElement[Numeric, Numeric]):
    """A numeric slider over an interval.

    Example:
        ```python
        slider = mo.ui.slider(start=1, stop=10, step=2)
        ```

        Or from a dataframe series:

        ```python
        slider = mo.ui.slider.from_series(df["column_name"])
        ```

        Or using numpy arrays:

        ```python
        import numpy as np

        # linear steps
        steps = np.array([1, 2, 3, 4, 5])
        slider = mo.ui.slider(steps=steps)
        # log steps
        log_slider = mo.ui.slider(steps=np.logspace(0, 3, 4))
        # power steps
        power_slider = mo.ui.slider(steps=np.power([1, 2, 3], 2))
        ```

    Attributes:
        value (Numeric): The current numeric value of the slider.
        start (Numeric): The minimum value of the interval.
        stop (Numeric): The maximum value of the interval.
        step (Optional[Numeric]): The slider increment.
        steps (Optional[Sequence[Numeric]]): List of steps.

    Args:
        start (Optional[Numeric]): The minimum value of the interval.
        stop (Optional[Numeric]): The maximum value of the interval.
        step (Optional[Numeric]): The slider increment.
        value (Optional[Numeric]): Default value.
        debounce (bool): Whether to debounce the slider to only send the value
            on mouse-up or drag-end. Defaults to False.
        disabled (bool, optional): Whether the slider is disabled. Defaults to False.
        orientation (Literal["horizontal", "vertical"]): The orientation of the
            slider, either "horizontal" or "vertical". Defaults to "horizontal".
        show_value (bool): Whether to display the current value of the slider.
            Defaults to False.
        include_input (bool): Whether to display an editable input with the current
            value of the slider. Defaults to False.
        steps (Optional[Sequence[Numeric]]): List of steps to customize the
            slider, mutually exclusive with `start`, `stop`, and `step`.
        label (str): Markdown label for the element. Defaults to an empty string.
        on_change (Optional[Callable[[Optional[Numeric]], None]]): Optional
            callback to run when this element's value changes.
        full_width (bool): Whether the input should take up the full width of
            its container. Defaults to False.

    Raises:
        ValueError: If `steps` is provided along with `start`, `stop`, or `step`.
        ValueError: If neither `steps` nor both `start` and `stop` are provided.
        ValueError: If `stop` is less than `start`.
        ValueError: If `value` is out of bounds.
        TypeError: If `steps` is not a sequence of numbers.

    Methods:
        from_series(series: DataFrameSeries, **kwargs: Any) -> slider:
            Create a slider from a dataframe series.

    """

    _name: Final[str] = "marimo-slider"
    _mapping: Optional[dict[int, Numeric]] = None

    def __init__(
        self,
        start: Optional[Numeric] = None,
        stop: Optional[Numeric] = None,
        step: Optional[Numeric] = None,
        value: Optional[Numeric] = None,
        debounce: bool = False,
        disabled: bool = False,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        show_value: bool = False,
        include_input: bool = False,
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
        warn_js_safe_number(start, stop, value)

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
            # Cast to a list in case user passes a numpy array
            if not isinstance(steps, list):
                steps = _convert_numpy_array(steps)
            self._dtype = _infer_dtype(steps)
            self._mapping = dict(enumerate(steps))
            try:
                # check if steps is a sequence of numbers
                assert all(isinstance(num, (int, float)) for num in steps)
                assert len(steps) > 0
                value = steps[0] if value is None else value
                value = steps.index(value)
            except ValueError:
                sys.stderr.write(
                    "Value out of bounds: default value should be in the steps"
                    ", set to first value.\n"
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
                    "disabled": disabled,
                    "orientation": orientation,
                    "show-value": show_value,
                    "include-input": include_input,
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
                    "disabled": disabled,
                    "orientation": orientation,
                    "show-value": show_value,
                    "include-input": include_input,
                    "full-width": full_width,
                },
                on_change=on_change,
            )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> slider:
        """Create a slider from a dataframe series."""
        info = get_number_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return slider(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(self, value: Numeric) -> Numeric:
        if self._mapping is not None:
            return cast(Numeric, self._dtype(self._mapping[int(value)]))
        return cast(Numeric, self._dtype(value))


@mddoc
class range_slider(UIElement[list[Numeric], Sequence[Numeric]]):
    """
    A numeric slider for specifying a range over an interval.

    Example:
        ```python
        range_slider = mo.ui.range_slider(
            start=1, stop=10, step=2, value=[2, 6]
        )
        ```

        Or from a dataframe series:

        ```python
        range_slider = mo.ui.range_slider.from_series(df["column_name"])
        ```

        Or using numpy arrays:

        ```python
        import numpy as np

        steps = np.array([1, 2, 3, 4, 5])
        # linear steps
        range_slider = mo.ui.range_slider(steps=steps)
        # log steps
        log_range_slider = mo.ui.range_slider(steps=np.logspace(0, 3, 4))
        # power steps
        power_range_slider = mo.ui.range_slider(steps=np.power([1, 2, 3], 2))
        ```

    Attributes:
        value (list[Numeric]): The current range value of the slider.
        start (Numeric): The minimum value of the interval.
        stop (Numeric): The maximum value of the interval.
        step (Optional[Numeric]): The slider increment.
        steps (Optional[Sequence[Numeric]]): List of steps.

    Args:
        start (Optional[Numeric]): The minimum value of the interval.
        stop (Optional[Numeric]): The maximum value of the interval.
        step (Optional[Numeric]): The slider increment.
        value (Optional[Sequence[Numeric]]): Default value.
        debounce (bool): Whether to debounce the slider to only send the value on mouse-up or drag-end.
        orientation (Literal["horizontal", "vertical"]): The orientation of the slider, either "horizontal" or "vertical".
        show_value (bool): Whether to display the current value of the slider.
        steps (Optional[Sequence[Numeric]]): List of steps to customize the slider, mutually exclusive with `start`, `stop`, and `step`.
        label (str): Markdown label for the element.
        on_change (Optional[Callable[[Sequence[Numeric]], None]]): Optional callback to run when this element's value changes.
        full_width (bool): Whether the input should take up the full width of its container.
        disabled (bool, optional): Whether the slider is disabled. Defaults to False.

    Methods:
        from_series(series: DataFrameSeries, **kwargs: Any) -> range_slider:
            Create a range slider from a dataframe series.
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
        disabled: bool = False,
    ) -> None:
        self.start: Numeric
        self.stop: Numeric
        self.step: Optional[Numeric]
        self.steps: Optional[Sequence[Numeric]]
        warn_js_safe_number(start, stop, *(value or []))

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
            # Cast to a list in case user passes a numpy array
            if not isinstance(steps, list):
                steps = _convert_numpy_array(steps)
            self._dtype = _infer_dtype(steps)
            self._mapping = dict(enumerate(steps))

            try:
                assert all(isinstance(num, (int, float)) for num in steps)
                assert len(steps) > 0
                value = [steps[0], steps[-1]] if value is None else value
                value = [steps.index(num) for num in value]
            except ValueError:
                sys.stderr.write(
                    "Value out of bounds: default value should be in the"
                    "steps, set to first and last values.\n"
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
                    "disabled": disabled,
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
                    "disabled": disabled,
                },
                on_change=on_change,
            )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> range_slider:
        """Create a range slider from a dataframe series."""
        info = get_number_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return range_slider(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(self, value: list[Numeric]) -> Sequence[Numeric]:
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
    """A boolean checkbox.

    Examples:
        ```python
        checkbox = mo.ui.checkbox()
        ```

    Attributes:
        value (bool): A boolean, True if checked.

    Args:
        value (bool, optional): Default value, True or False. Defaults to False.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[bool], None], optional): Optional callback to run when
            this element's value changes. Defaults to None.
        disabled (bool, optional): Whether the checkbox is disabled. Defaults to False.
    """

    _name: Final[str] = "marimo-checkbox"

    def __init__(
        self,
        value: bool = False,
        *,
        label: str = "",
        disabled: bool = False,
        on_change: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__(
            component_name=checkbox._name,
            initial_value=value,
            label=label,
            args={
                "disabled": disabled,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: bool) -> bool:
        return value


@mddoc
class radio(UIElement[Optional[str], Any]):
    """A radio group.

    Examples:
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

    Attributes:
        value (Any): The value of the selected radio option.
        options (dict): A dict mapping option name to option value.

    Args:
        options (Sequence[str] | dict[str, Any]): Sequence of text options, or dict
            mapping option name to option value.
        value (str, optional): Default option name, if None, starts with nothing
            checked. Defaults to None.
        inline (bool, optional): Whether to display options inline. Defaults to False.
        label (str, optional): Optional markdown label for the element. Defaults to "".
        on_change (Callable[[Any], None], optional): Optional callback to run when
            this element's value changes. Defaults to None.
        disabled (bool, optional): Whether the radio group is disabled. Defaults to False.
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
        disabled: bool = False,
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
                "disabled": disabled,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> radio:
        """Create a radio group from a dataframe series."""
        info = get_category_series_info(series)
        options = kwargs.pop("options", info.categories)
        label = kwargs.pop("label", info.label)
        return radio(options=options, label=label, **kwargs)

    def _convert_value(self, value: Optional[str]) -> Any:
        return self.options[value] if value is not None else None


@mddoc
class text(UIElement[str, str]):
    """A text input.

    Examples:
        ```python
        text = mo.ui.text(value="Hello, World!")
        ```

    Attributes:
        value (str): A string of the input's contents.

    Args:
        value (str, optional): Default value of text box. Defaults to "".
        placeholder (str, optional): Placeholder text to display when the text area
            is empty. Defaults to "".
        kind (Literal["text", "password", "email", "url"], optional): Input kind.
            Defaults to "text".
        max_length (int, optional): Maximum length of input. Defaults to None.
        disabled (bool, optional): Whether the input is disabled. Defaults to False.
        debounce (bool | int, optional): Whether the input is debounced. If number,
            debounce by that many milliseconds. If True, then value is only emitted
            on Enter or when the input loses focus. Defaults to True.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[str], None], optional): Optional callback to run when
            this element's value changes. Defaults to None.
        full_width (bool, optional): Whether the input should take up the full width
            of its container. Defaults to False.
    """

    _name: Final[str] = "marimo-text"

    def __init__(
        self,
        value: str = "",
        placeholder: str = "",
        kind: Literal["text", "password", "email", "url"] = "text",
        max_length: Optional[int] = None,
        disabled: bool = False,
        debounce: bool | int = True,
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
                "debounce": debounce,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: str) -> str:
        return value


@mddoc
class text_area(UIElement[str, str]):
    """A text area that is larger than `ui.text`.

    Examples:
        ```python
        text_area = mo.ui.text_area()
        ```

    Attributes:
        value (str): A string of the text area contents.

    Args:
        value (str, optional): Initial value of the text area. Defaults to "".
        placeholder (str, optional): Placeholder text to display when the text area
            is empty. Defaults to "".
        max_length (int, optional): Maximum length of input. Defaults to None.
        disabled (bool, optional): Whether the input is disabled. Defaults to False.
        debounce (bool | int, optional): Whether the input is debounced. If number,
            debounce by that many milliseconds. If True, then value is only emitted
            on Ctrl+Enter or when the input loses focus. Defaults to True.
        rows (int, optional): Number of rows of text to display. Defaults to None.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[str], None], optional): Optional callback to run when
            this element's value changes. Defaults to None.
        full_width (bool, optional): Whether the input should take up the full width
            of its container. Defaults to False.
    """

    _name: Final[str] = "marimo-text-area"

    def __init__(
        self,
        value: str = "",
        placeholder: str = "",
        max_length: Optional[int] = None,
        disabled: bool = False,
        debounce: bool | int = True,
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
                "debounce": debounce,
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

    Examples:
        ```python
        code_editor = mo.ui.code_editor()
        ```

    Attributes:
        value (str): A string of the code editor contents.

    Args:
        value (str, optional): Initial value of the code editor. Defaults to "".
        language (str, optional): Language of the code editor. Most major languages
            are supported, including "sql", "javascript", "typescript", "html",
            "css", "c", "cpp", "rust", and more. Defaults to "python".
        placeholder (str, optional): Placeholder text to display when the code editor
            is empty. Defaults to "".
        theme (Literal["light", "dark"], optional): Theme of the code editor.
            Defaults to the editor's default.
        disabled (bool, optional): Whether the input is disabled. Defaults to False.
        min_height (int, optional): Minimum height of the code editor in pixels.
            Defaults to None.
        max_height (int, optional): Maximum height of the code editor in pixels.
            Defaults to None.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[str], None], optional): Optional callback to run when
            this element's value changes. Defaults to None.
        show_copy_button (bool): Whether to show a button to copy the code
            to the clipboard. Defaults to True.
        debounce (bool | int, optional): Whether the input is debounced. If number,
            debounce by that many milliseconds. If True, then value is only emitted
            when the input loses focus. Defaults to False.
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
        show_copy_button: bool = True,
        debounce: bool | int = False,
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
                "show-copy-button": show_copy_button,
                "debounce": debounce,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: str) -> str:
        return value


def _to_option_name(option: Any) -> str:
    if isinstance(option, str):
        return option
    else:
        return repr(option)


@mddoc
class dropdown(UIElement[list[str], Any]):
    """A dropdown selector.

    Examples:
        ```python
        dropdown = mo.ui.dropdown(
            options=["a", "b", "c"], value="a", label="choose one"
        )

        # With search functionality
        dropdown = mo.ui.dropdown(
            options=["a", "b", "c"],
            value="a",
            label="choose one",
            searchable=True,
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

    Attributes:
        value (Any): The selected value, or None if no selection.
        options (dict): A dict mapping option name to option value.
        selected_key (str, optional): The selected option's key, or None if no selection.

    Args:
        options (Sequence[Any] | dict[str, Any]): Sequence of options, or dict
            mapping option name to option value.
            If the options are not strings, they will be converted to strings
            when displayed in the dropdown.
        value (str, optional): Default option name. Defaults to None.
        allow_select_none (bool, optional): Whether to include special option ("--")
            for a None value; when None, defaults to True when value is None.
            Defaults to None.
        searchable (bool, optional): Whether to enable search functionality.
            Defaults to False.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[Any], None], optional): Optional callback to run when
            this element's value changes. Defaults to None.
        full_width (bool, optional): Whether the input should take up the full width
            of its container. Defaults to False.
    """

    _MAX_OPTIONS: Final[int] = 1000
    _name: Final[str] = "marimo-dropdown"
    _selected_key: Optional[str] = None
    _RESERVED_OPTION: Final[str] = "--"

    def __init__(
        self,
        options: Sequence[Any] | dict[str, Any],
        value: Optional[Any] = None,
        allow_select_none: Optional[bool] = None,
        searchable: bool = False,
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
            options = {_to_option_name(option): option for option in options}

            if value is not None and not isinstance(value, str):
                value = _to_option_name(value)

        if self._RESERVED_OPTION in options:
            raise ValueError(
                f"The option name '{self._RESERVED_OPTION}' "
                "is reserved by marimo; please use another name."
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
                "searchable": searchable,
                "full-width": full_width,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> dropdown:
        """Create a dropdown from a dataframe series."""
        info = get_category_series_info(series)
        options = kwargs.pop("options", info.categories)
        label = kwargs.pop("label", info.label)
        return dropdown(options=options, label=label, **kwargs)

    def _convert_value(self, value: list[str]) -> Any:
        if value:
            assert len(value) == 1, "Dropdowns only support a single value"
            self._selected_key = value[0]
            if self._selected_key not in self.options:
                raise ValueError(
                    f"The option name '{self._selected_key}' "
                    "is not a valid option. "
                    "Please use one of the following options: "
                    f"{list(self.options.keys())}"
                )
            return self.options[value[0]]
        else:
            self._selected_key = None
            return None

    @property
    def selected_key(self) -> Optional[str]:
        """The selected option's key, or `None` if no selection."""
        return self._selected_key


@mddoc
class multiselect(UIElement[list[str], list[object]]):
    """A multiselect input.

    Examples:
        ```python
        multiselect = mo.ui.multiselect(
            options=["a", "b", "c"], label="choose some options"
        )
        ```

        Or from a dataframe series:
        ```python
        multiselect = mo.ui.multiselect.from_series(df["column_name"])
        ```

    Attributes:
        value (List[object]): The selected values, or None if no selection.
        options (dict): A dict mapping option name to option value.

    Args:
        options (Sequence[Any] | dict[str, Any]): Sequence of options, or dict
            mapping option name to option value.
            If the options are not strings, they will be converted to strings
            when displayed in the dropdown.
        value (Sequence[str], optional): A list of initially selected options.
            Defaults to None.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[List[object]], None], optional): Optional callback to run
            when this element's value changes. Defaults to None.
        full_width (bool, optional): Whether the input should take up the full width
            of its container. Defaults to False.
        max_selections (int, optional): Maximum number of items that can be selected.
            Defaults to None.
    """

    _MAX_OPTIONS: Final[int] = 100000
    _name: Final[str] = "marimo-multiselect"

    def __init__(
        self,
        options: Sequence[Any] | dict[str, Any],
        value: Optional[Sequence[Any]] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[list[object]], None]] = None,
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
            options = {_to_option_name(option): option for option in options}

            if value is not None and not isinstance(value, str):
                value = [_to_option_name(v) for v in value]

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
    def from_series(series: DataFrameSeries, **kwargs: Any) -> multiselect:
        """Create a multiselect from a dataframe series."""
        info = get_category_series_info(series)
        options = kwargs.pop("options", info.categories)
        label = kwargs.pop("label", info.label)
        return multiselect(options=options, label=label, **kwargs)

    def _convert_value(self, value: list[str]) -> list[object]:
        return [self.options[v] for v in value]


@mddoc
class button(UIElement[Any, Any]):
    """A button with an optional callback and optional value.

    Examples:
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

    Attributes:
        value (Any): The value of the button.

    Args:
        on_click (Callable[[Any], Any], optional): A callable called on click that
            takes the current value of the button and returns a new value.
            Defaults to None.
        value (Any, optional): An initial value for the button. Defaults to None.
        kind (Literal["neutral", "success", "warn", "danger"], optional): Button
            style. Defaults to "neutral".
        disabled (bool, optional): Whether the button is disabled. Defaults to False.
        tooltip (str, optional): Tooltip text for the button. Defaults to None.
        label (str, optional): Markdown label for the element. Defaults to "click here".
        on_change (Callable[[Any], None], optional): Optional callback to run when
            this element's value changes. Defaults to None.
        full_width (bool, optional): Whether the input should take up the full width
            of its container. Defaults to False.
        keyboard_shortcut (str, optional): Keyboard shortcut to trigger the button
            (e.g. 'Ctrl-L'). Defaults to None.
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
        keyboard_shortcut: Optional[str] = None,
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
                "keyboard-shortcut": keyboard_shortcut,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: Any) -> Any:
        if value == 0:
            # frontend's value == 0 only during initialization; first value
            # frontend will send is 1
            return self._initial_value
        try:
            return self._on_click(self._value)  # type: ignore[no-untyped-call]
        except Exception:
            sys.stderr.write(
                f"on_click handler for button ({str(self)}) raised an Exception:\n {traceback.format_exc()}\n"
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
class file(UIElement[list[tuple[str, str]], Sequence[FileUploadResults]]):
    """A button or drag-and-drop area to upload a file.

    Once a file is uploaded, the UI element's value is a list of namedtuples
    (name, contents), where name is the filename and contents is the contents
    of the file. Alternatively, use the methods name(index: int = 0) and
    contents(index: int = 0) to retrieve the name or contents of the file at a
    specified index.

    Use the kind argument to switch between a button and a drag-and-drop area.

    The maximum file size is 100MB.

    Examples:
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

    Attributes:
        value (Sequence[FileUploadResults]): A sequence of FileUploadResults,
            which have string name and bytes contents fields.

    Methods:
        name(index: int = 0) -> Optional[str]: Get the name of the uploaded file
            at index.
        contents(index: int = 0) -> Optional[bytes]: Get the contents of the
            uploaded file at index.

    Args:
        filetypes (Sequence[str], optional): The file types accepted; for example,
            filetypes=[".png", ".jpg"]. If None, all files are accepted.
            In addition to extensions, you may provide "audio/*", "video/*",
            or "image/*" to accept any audio, video, or image file.
            Defaults to None.
        multiple (bool, optional): If True, allow the user to upload multiple
            files. Defaults to False.
        kind (Literal["button", "area"], optional): Type of upload interface.
            Defaults to "button".
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[Sequence[FileUploadResults]], None], optional):
            Optional callback to run when this element's value changes.
            Defaults to None.
        max_size (int, optional): The maximum size of the file to upload
            (in bytes). Defaults to 100MB.
    """

    _name: Final[str] = "marimo-file"

    def __init__(
        self,
        filetypes: Optional[Sequence[str]] = None,
        multiple: bool = False,
        kind: Literal["button", "area"] = "button",
        *,
        max_size: int = 100_000_000,  # 100MB default
        label: str = "",
        on_change: Optional[
            Callable[[Sequence[FileUploadResults]], None]
        ] = None,
    ) -> None:
        # Validate filetypes have leading dots or contain a forward slash
        if filetypes is not None:
            invalid_types = [
                ft for ft in filetypes if not (ft.startswith(".") or "/" in ft)
            ]
            if invalid_types:
                raise ValueError(
                    f"File types must start with a dot (e.g., '.csv' instead of 'csv') "
                    f"or contain a forward slash (e.g., 'application/json'). "
                    f"Invalid types: {', '.join(invalid_types)}"
                )

        if max_size <= 0:
            raise ValueError("max_size must be greater than 0")

        super().__init__(
            component_name=file._name,
            initial_value=[],
            label=label,
            args={
                "filetypes": filetypes if filetypes is not None else [],
                "multiple": multiple,
                "kind": kind,
                "max_size": max_size,
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
        """Get file name at index.

        Args:
            index (int, optional): Index of the file to get the name from.
                Defaults to 0.

        Returns:
            Optional[str]: The name of the file at the specified index,
                or None if index is out of range.
        """
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].name

    def contents(self, index: int = 0) -> Optional[bytes]:
        """Get file contents at index.

        Args:
            index (int, optional): Index of the file to get the contents from.
                Defaults to 0.

        Returns:
            Optional[bytes]: The contents of the file at the specified index,
                or None if index is out of range.
        """
        if not self.value or index >= len(self.value):
            return None
        else:
            return self.value[index].contents


T = TypeVar("T")


@dataclasses.dataclass
class ValueArgs:
    value: Optional[JSONType] = None


@mddoc
class form(UIElement[Optional[JSONTypeBound], Optional[T]]):
    """A submittable form linked to a UIElement.

    Use a `form` to prevent sending UI element values to Python until a button
    is clicked.

    The value of a `form` is the value of the underlying element the last time
    the form was submitted.

    Examples:
        Create a form with chaining:
        ```python
        # Create a form with chaining
        form = mo.ui.slider(1, 100).form()
        ```

        Create a form with multiple elements:
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

        Instantiate a form directly:
        ```python
        # Instantiate a form directly
        form = mo.ui.form(element=mo.ui.slider(1, 100))
        ```

    Attributes:
        value (Any): The value of the wrapped element when the form's submit
            button was last clicked.
        element (UIElement): A copy of the wrapped element.

    Args:
        element (UIElement[JSONTypeBound, T]): The element to wrap.
        bordered (bool, optional): Whether the form should have a border.
            Defaults to True.
        loading (bool, optional): Whether the form should be in a loading state.
            Defaults to False.
        submit_button_label (str, optional): The label of the submit button.
            Defaults to "Submit".
        submit_button_tooltip (str, optional): The tooltip of the submit button.
            Defaults to None.
        submit_button_disabled (bool, optional): Whether the submit button should
            be disabled. Defaults to False.
        clear_on_submit (bool, optional): Whether the form should clear its
            contents after submitting. Defaults to False.
        show_clear_button (bool, optional): Whether the form should show a clear
            button. Defaults to False.
        clear_button_label (str, optional): The label of the clear button.
            Defaults to "Clear".
        clear_button_tooltip (str, optional): The tooltip of the clear button.
            Defaults to None.
        validate (Callable[[Optional[JSONType]], Optional[str]], optional): A
            function that takes the form's value and returns an error message if
            the value is invalid, or None if the value is valid. Defaults to None.
        label (str, optional): Markdown label for the form. Defaults to "".
        on_change (Callable[[Optional[T]], None], optional): Optional callback to
            run when this element's value changes. Defaults to None.
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


def _convert_numpy_array(steps: Any) -> list[Numeric]:
    """Convert numpy array to list if needed."""
    if DependencyManager.numpy.imported():
        import numpy as np

        if isinstance(steps, np.ndarray):
            return steps.tolist()  # type: ignore[return-value,no-any-return]
    return steps  # type: ignore[no-any-return]
