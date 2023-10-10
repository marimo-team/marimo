# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import base64
import datetime as dt
import traceback
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
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
from marimo._output.mime import MIME
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import S as JSONTypeBound
from marimo._plugins.ui._core.ui_element import UIElement

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

    **Attributes.**

    - `value`: the current numeric value of the slider
    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the slider increment

    **Initialization Args.**

    - `start`: the minimum value of the interval
    - `stop`: the maximum value of the interval
    - `step`: the slider increment
    - `value`: default value
    - `debounce`: whether to debounce the slider to only send
        the value on mouse-up or drag-end
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-slider"

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
    ) -> None:
        self._dtype = (
            float
            if any(
                isinstance(num, float) for num in (start, stop, step, value)
            )
            else int
        )
        value = start if value is None else value

        if stop < start:
            raise ValueError(
                f"Invalid bounds: stop value ({stop}) must be greater than "
                f"start value ({start})"
            )
        elif value < start or value > stop:
            raise ValueError(
                f"Value out of bounds: default value ({value}) must be "
                f"greater than start ({start}) and less than stop ({stop})."
            )

        # minimum value of interval
        self.start = start
        # maximum value of interval
        self.stop = stop
        # slider increment
        self.step = step

        super().__init__(
            component_name=slider._name,
            initial_value=value,
            label=label,
            args={
                "start": start,
                "stop": stop,
                "step": step if step is not None else None,
                "debounce": debounce,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: Numeric) -> Numeric:
        return cast(Numeric, self._dtype(value))


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
      options=['a', 'b', 'c'],
      value='a',
      label='choose one'
    )
    ```

    ```python
    radiogroup = mo.ui.radio(
      options={'one': 1, 'two': 2, 'three': 3},
      value='one',
      label='pick a number'
    )
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
            },
            on_change=on_change,
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
      options=['a', 'b', 'c'],
      value='a',
      label='choose one'
    )
    ```

    ```python
    dropdown = mo.ui.dropdown(
      options={'one': 1, 'two': 2, 'three': 3},
      value='one',
      label='pick a number'
    )
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
      options=['a', 'b', 'c'],
      label='choose some options'
    )
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
    """

    _name: Final[str] = "marimo-multiselect"

    def __init__(
        self,
        options: Sequence[str] | dict[str, Any],
        value: Optional[Sequence[str]] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[List[object]], None]] = None,
        full_width: bool = False,
    ) -> None:
        if not isinstance(options, dict):
            options = {option: option for option in options}

        self.options = options
        initial_value = list(value) if value is not None else []

        super().__init__(
            component_name=multiselect._name,
            initial_value=initial_value,
            label=label,
            args={
                "options": list(self.options.keys()),
                "full-width": full_width,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: list[str]) -> list[object]:
        return [self.options[v] for v in value]


@mddoc
class table(UIElement[List[str], List[object]]):
    """
    A table component.

    **Example.**

    ```python
    table = mo.ui.table(
      data=[
        {'first_name': 'Michael', 'last_name': 'Scott'},
        {'first_name': 'Dwight', 'last_name': 'Schrute'}
      ],
      label='Users'
    )
    ```

    ```python
    # df is a Pandas dataframe
    table = mo.ui.table(
        data=df.to_dict('records'),
        # use pagination when your table has many rows
        pagination=True,
        label='Dataset'
    )
    ```

    **Attributes.**

    - `value`: the selected values, or `None` if no selection.
    - `data`: the table data

    **Initialization Args.**

    - `data`:  a list of values representing a column, or a list of dicts
        where each dict represents a row in the table
        (mapping column names to values). values can be
        primitives (`str`, `int`, `float`, `bool`, or `None`)
        or Marimo elements: e.g.
        `mo.ui.button(...)`, `mo.md(...)`, `mo.as_html(...)`, etc.
    - `pagination`: whether to paginate; if `False`, all rows will be shown
    - `selection`: 'single' or 'multi' to enable row selection, or `None` to
        disable
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-table"

    def __init__(
        self,
        data: Sequence[str | int | float | bool | MIME | None]
        | Sequence[dict[str, str | int | float | bool | MIME | None]],
        pagination: bool = False,
        selection: Optional[Literal["single", "multi"]] = "multi",
        *,
        label: str = "",
        on_change: Optional[Callable[[List[object]], None]] = None,
    ) -> None:
        if not isinstance(data, (list, tuple)):
            raise ValueError("data must be a list or tuple.")

        self._data = data
        if not isinstance(data[0], dict) and isinstance(
            data[0], (str, int, float, bool, type(None))
        ):
            # we're going to assume that data has the right shape, after
            # having checked just the first entry
            data = cast(List[Union[str, int, float, bool, MIME, None]], data)
            data = [{"value": datum} for datum in data]
        elif not isinstance(data[0], dict):
            raise ValueError(
                "data must be a sequence of JSON-serializable types, or a "
                "sequence of dicts."
            )

        super().__init__(
            component_name=table._name,
            label=label,
            initial_value=[],
            args={
                "data": data,
                "pagination": pagination,
                "selection": selection,
            },
            on_change=on_change,
        )

    @property
    def data(
        self,
    ) -> Union[
        Sequence[str | int | float | bool | None],
        Sequence[dict[str, str | int | float | bool | None]],
    ]:
        return self._data

    def _convert_value(self, value: list[str]) -> list[object]:
        return [self._data[int(v)] for v in value]


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
      value=0,
      on_click=lambda value: value + 1,
      label='increment'
    )

    # adding intent
    delete_button = mo.ui.button(
        label='Do not click',
        kind='danger',
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
        *,
        label: str = "click here",
        on_change: Optional[Callable[[Any], None]] = None,
        full_width: bool = False,
    ) -> None:
        self._on_click = (lambda _: value) if on_click is None else on_click
        self._initial_value = value
        super().__init__(
            component_name=button._name,
            # frontend's value is always a counter
            initial_value=0,
            label=label,
            args={
                "kind": kind,
                "disabled": disabled,
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


@mddoc
class file(UIElement[List[Tuple[str, str]], Sequence[FileUploadResults]]):
    """
    A button or drag-and-drop area to upload a file.

    Once a file is uploaded, the UI element's value is a list of
    `namedtuples (name, contents)`, where `name` is the filename and
    `contents` is the contents of the file. Alternatively, use the methods
    `name(index: int = 0)` and `contents(index: int = 0)` to retrieve the
    name or contents of the file at a specified index.

    Use the `kind` argument to switch between a button and a drop-and-drop
    area.

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
    f = mo.ui.file(
      filetypes=[".png", ".jpg"], multiple=True)

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

    def _convert_value(self, value: str) -> dt.date:
        return dt.datetime.strptime(value, self.DATEFORMAT).date()

    @property
    def start(self) -> dt.date:
        return self._start

    @property
    def stop(self) -> dt.date:
        return self._stop


T = TypeVar("T")


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
    form = mo.md('''
        **Your form.**

        {name}

        {date}
    ''').batch(
        name=mo.ui.text(label='name'),
        date=mo.ui.date(label='date'),
    ).form()
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
    - `label`: text label for the form
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-form"

    def __init__(
        self,
        element: UIElement[JSONTypeBound, T],
        *,
        label: str = "",
        on_change: Optional[Callable[[Optional[T]], None]] = None,
    ) -> None:
        self.element = element._clone()
        super().__init__(
            component_name=form._name,
            initial_value=None,
            label=label,
            args={"element-id": self.element._id},
            slotted_html=self.element.text,
            on_change=on_change,
        )

    def _convert_value(self, value: Optional[JSONTypeBound]) -> Optional[T]:
        if value is None:
            return None
        self.element._update(value)
        return self.element.value

    def _clone(self) -> form[JSONTypeBound, T]:
        return form(element=self.element)
