# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime as dt
from typing import (
    Any,
    Callable,
    Final,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)

from marimo import _loggers
from marimo._data.series import (
    DataFrameSeries,
    get_date_series_info,
    get_datetime_series_info,
)
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]
TypeName = Literal["date", "datetime"]

T = TypeVar("T", dt.date, dt.datetime)

DATE_FORMAT = "%Y-%m-%d"


def convert_str_to_date(value: Union[str, dt.date, dt.datetime]) -> dt.date:
    """Convert a string or date to a date object.

    Args:
        value: A string in YYYY-MM-DD format, a date, or a datetime object.

    Returns:
        A date object.
    """
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    return dt.datetime.strptime(value, DATE_FORMAT).date()


@overload
def convert_str_to_datetime(value: str) -> dt.datetime: ...


@overload
def convert_str_to_datetime(value: None) -> None: ...


def convert_str_to_datetime(
    value: Union[str, None],
) -> Union[dt.datetime, None]:
    """Convert a string to a datetime object.

    Args:
        value: A string in various datetime formats or None.

    Returns:
        A datetime object or None.
    """
    if value is None:
        return None
    POSSIBLE_FORMATS = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%dT%H",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    )
    for fmt in POSSIBLE_FORMATS:
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError(f"Invalid datetime format: {value}")


def validate_start_stop(
    start: T, stop: T, type_name: TypeName = "date"
) -> None:
    """Validate that stop is greater than start.

    Args:
        start: The start date/datetime.
        stop: The stop date/datetime.
        type_name: The type name for error messages ('date' or 'datetime').

    Raises:
        ValueError: If stop is not greater than start.
    """
    if stop < start:
        raise ValueError(
            f"The stop {type_name} ({stop}) must be greater than "
            f"the start {type_name} ({start})"
        )


def get_default_value(
    start: Optional[T],
    stop: Optional[T],
    today_value: T,
) -> T:
    """Get the default value when none is provided.

    Args:
        start: The start date/datetime, or None.
        stop: The stop date/datetime, or None.
        today_value: The value to use when both start and stop are None.

    Returns:
        The default value.
    """
    if start is None and stop is None:
        return today_value
    elif start is not None:
        return start
    else:
        return cast(T, stop)


def validate_value_within_bounds(
    value: T, start: T, stop: T, type_name: TypeName = "date"
) -> None:
    """Validate that a value is within the start/stop bounds.

    Args:
        value: The value to validate.
        start: The minimum allowed value.
        stop: The maximum allowed value.
        type_name: The type name for error messages ('date' or 'datetime').

    Raises:
        ValueError: If value is outside the bounds.
    """
    if value < start or value > stop:
        raise ValueError(
            f"The default value ({value}) must be greater than "
            f"the start {type_name} ({start}) and less than the stop "
            f"{type_name} ({stop})."
        )


def validate_range_within_bounds(
    range_value: tuple[T, T],
    start: T,
    stop: T,
    type_name: TypeName = "date",
) -> None:
    """Validate that a range value is within bounds and properly ordered.

    Args:
        range_value: A tuple of (start_value, end_value).
        start: The minimum allowed value.
        stop: The maximum allowed value.
        type_name: The type name for error messages ('date' or 'datetime').

    Raises:
        ValueError: If value is outside bounds or improperly ordered.
    """
    left, right = range_value
    if left < start or right > stop or left > right:
        raise ValueError(
            f"The default value ({range_value}) must be within "
            f"the range [{start}, {stop}] and the first {type_name} "
            f"must not be greater than the second {type_name}."
        )


@mddoc
class date(UIElement[str, dt.date]):
    """A date picker with an optional start and stop date.

    Examples:
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

    Attributes:
        value (str | datetime.date): A str (YYYY-MM-DD) or `datetime.date` object of the chosen date.
        start (datetime.date): The start date.
        stop (datetime.date): The stop date.

    Args:
        start (datetime.date | str, optional): Minimum date selectable. If None, defaults to 01-01-0001.
        stop (datetime.date | str, optional): Maximum date selectable. If None, defaults to 12-31-9999.
        value (datetime.date | str, optional): Default date.
            If None and start and stop are None, defaults to the current day.
            If None and start is not None, defaults to start.
            If None and stop is not None, defaults to stop.
        label (str, optional): Markdown label for the element.
        on_change (Callable[[datetime.date], None], optional): Optional callback to run when this element's value changes.
        full_width (bool, optional): Whether the input should take up the full width of its container.
        disabled (bool, optional): Whether the input should be disabled.
    """

    _name: Final[str] = "marimo-date"

    DATE_FORMAT = "%Y-%m-%d"

    def __init__(
        self,
        start: Optional[dt.date | str] = None,
        stop: Optional[dt.date | str] = None,
        value: Optional[dt.date | str] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[dt.date], None]] = None,
        full_width: bool = False,
        disabled: bool = False,
    ) -> None:
        if isinstance(start, str):
            start = convert_str_to_date(start)
        if isinstance(stop, str):
            stop = convert_str_to_date(stop)
        if isinstance(value, str):
            value = convert_str_to_date(value)

        self._start = dt.date(dt.MINYEAR, 1, 1) if start is None else start
        self._stop = dt.date(dt.MAXYEAR, 12, 31) if stop is None else stop

        validate_start_stop(self._start, self._stop, "date")

        if value is None:
            value = get_default_value(start, stop, dt.date.today())
        value = cast(dt.date, value)

        validate_value_within_bounds(value, self._start, self._stop, "date")

        super().__init__(
            component_name=date._name,
            initial_value=value.isoformat(),
            label=label,
            args={
                "start": self._start.isoformat(),
                "stop": self._stop.isoformat(),
                "full-width": full_width,
                "disabled": disabled,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> date:
        """Create a date picker from a dataframe series.

        Args:
            series (DataFrameSeries): A pandas Series containing datetime values.
            **kwargs: Additional keyword arguments passed to the date picker constructor.
                Supported arguments: start, stop, label, and any other date picker parameters.

        Returns:
            date: A date picker initialized with the series' min and max dates as bounds.
        """
        info = get_date_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return date(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(self, value: str) -> dt.date:
        return convert_str_to_date(value)

    @property
    def start(self) -> dt.date:
        """Get the minimum selectable date.

        Returns:
            datetime.date: The start date, which is either the user-specified minimum date
                or 01-01-0001 if no start date was specified.
        """
        return self._start

    @property
    def stop(self) -> dt.date:
        """Get the maximum selectable date.

        Returns:
            datetime.date: The stop date, which is either the user-specified maximum date
                or 12-31-9999 if no stop date was specified.
        """
        return self._stop


@mddoc
class datetime(UIElement[Optional[str], Optional[dt.datetime]]):
    """A datetime picker over an interval.

    Examples:
        ```python
        datetime_picker = mo.ui.datetime(
            start=dt.datetime(2023, 1, 1),
            stop=dt.datetime(2023, 12, 31, 23, 59, 59),
        )
        ```

        Or from a dataframe series:

        ```python
        datetime_picker = mo.ui.datetime.from_series(df["datetime_column"])
        ```

    Attributes:
        value (datetime.datetime, optional): The selected datetime, possibly None.
        start (datetime.datetime): The minimum selectable datetime.
        stop (datetime.datetime): The maximum selectable datetime.

    Args:
        start (datetime.datetime | str, optional): The minimum selectable datetime. Defaults to minimum datetime.
        stop (datetime.datetime | str, optional): The maximum selectable datetime. Defaults to maximum datetime.
        value (datetime.datetime | str, optional): Default value.
        precision (Literal["hour", "minute", "second"], optional): The precision of the datetime picker. Defaults to "minute".
        label (str, optional): Markdown label for the element.
        on_change (Callable[[Optional[datetime.datetime]], None], optional): Optional callback to run when this element's value changes.
        full_width (bool, optional): Whether the input should take up the full width of its container.
        disabled (bool, optional): Whether the input should be disabled. Defaults to False.
    """

    _name: Final[str] = "marimo-datetime"
    DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S"

    def __init__(
        self,
        start: Optional[dt.datetime | str] = None,
        stop: Optional[dt.datetime | str] = None,
        value: Optional[dt.datetime | str] = None,
        *,
        precision: Literal["hour", "minute", "second"] = "minute",
        label: Optional[str] = None,
        on_change: Optional[Callable[[Optional[dt.datetime]], None]] = None,
        full_width: bool = False,
        disabled: bool = False,
    ):
        if isinstance(start, str):
            start = convert_str_to_datetime(start)
        if isinstance(stop, str):
            stop = convert_str_to_datetime(stop)
        if isinstance(value, str):
            value = convert_str_to_datetime(value)

        if precision not in ("hour", "minute", "second"):
            raise ValueError(
                f"precision must be 'hour', 'minute', or 'second', got {precision}"
            )

        self._start = dt.datetime.min if start is None else start
        self._stop = dt.datetime.max if stop is None else stop
        self._precision = precision

        validate_start_stop(self._start, self._stop, "datetime")

        if value is None:
            value = get_default_value(start, stop, dt.datetime.today())
        value = cast(dt.datetime, value)

        validate_value_within_bounds(
            value, self._start, self._stop, "datetime"
        )

        super().__init__(
            component_name=datetime._name,
            initial_value=value.isoformat(timespec="seconds"),
            label=label,
            args={
                "start": self._start.isoformat(timespec="seconds"),
                "stop": self._stop.isoformat(timespec="seconds"),
                "precision": precision,
                "full-width": full_width,
                "disabled": disabled,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> datetime:
        """Create a datetime picker from a dataframe series.

        Args:
            series (DataFrameSeries): A pandas Series containing datetime values.
            **kwargs: Additional keyword arguments passed to the datetime picker constructor.
                Supported arguments: start, stop, label, and any other datetime picker parameters.

        Returns:
            datetime: A datetime picker initialized with the series' min and max datetimes as bounds.
        """
        info = get_datetime_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return datetime(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(self, value: Optional[str]) -> Optional[dt.datetime]:
        return convert_str_to_datetime(value)

    @property
    def start(self) -> dt.datetime:
        """Get the minimum selectable datetime.

        Returns:
            datetime.datetime: The start datetime, which is either the user-specified minimum
                datetime or datetime.min if no start datetime was specified.
        """
        return self._start

    @property
    def stop(self) -> dt.datetime:
        """Get the maximum selectable datetime.

        Returns:
            datetime.datetime: The stop datetime, which is either the user-specified maximum
                datetime or datetime.max if no stop datetime was specified.
        """
        return self._stop


@mddoc
class date_range(UIElement[tuple[str, str], tuple[dt.date, dt.date]]):
    """A date range picker over an interval.

    Examples:
        ```python
        date_range = mo.ui.date_range(
            start=dt.date(2023, 1, 1), stop=dt.date(2023, 12, 31)
        )
        ```

        Or from a dataframe series:

        ```python
        date_range = mo.ui.date_range.from_series(df["date_column"])
        ```

    Attributes:
        value (Tuple[datetime.date, datetime.date]): A tuple of (start_date, end_date) representing the selected range.
        start (datetime.date): The minimum selectable date.
        stop (datetime.date): The maximum selectable date.

    Args:
        start (datetime.date | str, optional): Minimum date selectable. If None, defaults to 01-01-0001.
        stop (datetime.date | str, optional): Maximum date selectable. If None, defaults to 12-31-9999.
        value (Tuple[datetime.date | str, datetime.date | str], optional): Default value as (start_date, end_date).
            If None, defaults to (start, stop) if provided, otherwise today's date for both.
        label (str, optional): Markdown label for the element.
        on_change (Callable[[Tuple[datetime.date, datetime.date]], None], optional): Optional callback to run when this element's value changes.
        full_width (bool, optional): Whether the input should take up the full width of its container.
        disabled (bool, optional): Whether the input should be disabled.
    """

    _name: Final[str] = "marimo-date-range"
    DATEFORMAT: Final[str] = "%Y-%m-%d"

    def __init__(
        self,
        start: Optional[dt.date | str] = None,
        stop: Optional[dt.date | str] = None,
        value: Optional[tuple[dt.date, dt.date] | tuple[str, str]] = None,
        *,
        label: Optional[str] = None,
        on_change: Optional[Callable[[tuple[dt.date, dt.date]], None]] = None,
        full_width: bool = False,
        disabled: bool = False,
    ):
        if isinstance(start, str):
            start = convert_str_to_date(start)
        if isinstance(stop, str):
            stop = convert_str_to_date(stop)
        if value is not None:
            value = (
                convert_str_to_date(value[0]),
                convert_str_to_date(value[1]),
            )

        self._start = dt.date(dt.MINYEAR, 1, 1) if start is None else start
        self._stop = dt.date(dt.MAXYEAR, 12, 31) if stop is None else stop

        validate_start_stop(self._start, self._stop, "date")

        if value is None:
            if start is None or stop is None:
                value = (dt.date.today(), dt.date.today())
            else:
                value = (start, stop)

        validate_range_within_bounds(value, self._start, self._stop, "date")

        super().__init__(
            component_name=date_range._name,
            initial_value=(value[0].isoformat(), value[1].isoformat()),
            label=label,
            args={
                "start": self._start.isoformat(),
                "stop": self._stop.isoformat(),
                "full-width": full_width,
                "disabled": disabled,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> date_range:
        """Create a date range picker from a dataframe series.

        Args:
            series (DataFrameSeries): A pandas Series containing datetime values.
            **kwargs: Additional keyword arguments passed to the date range picker constructor.
                Supported arguments: start, stop, label, and any other date range picker parameters.

        Returns:
            date_range: A date range picker initialized with the series' min and max dates as bounds.
        """
        info = get_date_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return date_range(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(
        self, value: tuple[str, str]
    ) -> tuple[dt.date, dt.date]:
        return convert_str_to_date(value[0]), convert_str_to_date(value[1])

    @property
    def start(self) -> dt.date:
        """Get the minimum selectable date.

        Returns:
            datetime.date: The start date, which is either the user-specified minimum date
                or 01-01-0001 if no start date was specified.
        """
        return self._start

    @property
    def stop(self) -> dt.date:
        """Get the maximum selectable date.

        Returns:
            datetime.date: The stop date, which is either the user-specified maximum date
                or 12-31-9999 if no stop date was specified.
        """
        return self._stop


@mddoc
class date_slider(UIElement[list[str], tuple[dt.date, dt.date]]):
    """A date slider picker over an interval.

    Examples:
        ```python
        date_slider = mo.ui.date_slider(
            start=dt.date(2023, 1, 1),
            stop=dt.date(2023, 12, 31),
            step=dt.timedelta(days=7),
        )
        ```

        Or from a dataframe series:

        ```python
        date_slider = mo.ui.date_slider.from_series(
            df["date_column"], step=dt.timedelta(days=7)
        )
        ```

    Attributes:
        value (Tuple[datetime.date, datetime.date]): A tuple of (start_date, end_date) representing the selected range.
        start (datetime.date): The minimum selectable date.
        stop (datetime.date): The maximum selectable date.
        step (Optional[datetime.timedelta]): The slider increment.

    Args:
        start (datetime.date | str, optional): Minimum date selectable. If None, defaults to 01-01-0001.
        stop (datetime.date | str, optional): Maximum date selectable. If None, defaults to 12-31-9999.
        step (Optional[datetime.timedelta]): The slider increment. If None, defaults to 1 day.
        value (Tuple[datetime.date | str, datetime.date | str], optional): Default value as (start_date, end_date).
            If None, defaults to (start, stop) if provided, otherwise today's date for both.
        debounce (bool, optional): Whether to debounce the slider to only send the value on mouse-up or drag-end.
            Defaults to False.
        orientation (Literal["horizontal", "vertical"], optional): The orientation of the slider, either "horizontal"
            or "vertical". Defaults to "horizontal".
        show_value (bool, optional): Whether to display the current value of the slider. Defaults to False.
        label (str, optional): Markdown label for the element.
        on_change (Callable[[Tuple[datetime.date, datetime.date]], None], optional): Optional callback to run when
            this element's value changes.
        full_width (bool, optional): Whether the input should take up the full width of its container.
        disabled (bool, optional): Whether the input should be disabled.

    Methods:
        from_series(series: DataFrameSeries, **kwargs: Any) -> date_slider:
            Create a date slider from a dataframe series.
    """

    _name: Final[str] = "marimo-date-slider"
    DATEFORMAT: Final[str] = "%Y-%m-%d"
    _mapping: Optional[dict[int, dt.date]] = None

    def __init__(
        self,
        start: Optional[dt.date | str] = None,
        stop: Optional[dt.date | str] = None,
        step: Optional[dt.timedelta] = None,
        value: Optional[tuple[dt.date, dt.date] | tuple[str, str]] = None,
        debounce: bool = False,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        show_value: bool = False,
        *,
        label: Optional[str] = None,
        on_change: Optional[Callable[[tuple[dt.date, dt.date]], None]] = None,
        full_width: bool = False,
        disabled: bool = False,
    ):
        if isinstance(start, str):
            start = convert_str_to_date(start)
        if isinstance(stop, str):
            stop = convert_str_to_date(stop)
        # TODO(FBruzzesi): Allow `step` to be in string format (e.g. 1d) instead of timedelta
        # and parse it into timedelta?
        if value is not None:
            value = (
                convert_str_to_date(value[0]),
                convert_str_to_date(value[1]),
            )

        self._start = dt.date(dt.MINYEAR, 1, 1) if start is None else start
        self._stop = dt.date(dt.MAXYEAR, 12, 31) if stop is None else stop
        self._step = dt.timedelta(days=1) if step is None else step

        validate_start_stop(self._start, self._stop, "date")

        if not isinstance(self._step, dt.timedelta):
            msg = f"Expected `step` of type datetime.timedelta. Found {type(self._step)} instead."
            raise TypeError(msg)

        if self._step.total_seconds() <= 0:
            raise ValueError(f"The step ({step}) must be a positive timedelta")

        # Generate list of dates based on start, stop, and step
        dates_list = []
        current = self._start
        while current <= self._stop:
            dates_list.append(current)
            current += self._step

        if not dates_list:
            raise ValueError(
                f"No valid dates generated between {start} and {stop} "
                f"with step {step}"
            )

        # Indices to dates mapping
        self._mapping = dict(enumerate(dates_list))

        if value is None:
            if start is None or stop is None:
                value = (dt.date.today(), dt.date.today())
            else:
                value = (start, stop)

        validate_range_within_bounds(value, self._start, self._stop, "date")

        # Find closest dates for the value
        try:
            start_date = dates_list[
                self._find_closest_index(value[0], dates_list)
            ]
            stop_date = dates_list[
                self._find_closest_index(value[1], dates_list)
            ]
        except ValueError as exc:
            raise ValueError(
                f"Could not find valid dates for value {value}: {exc}"
            ) from exc

        super().__init__(
            component_name=date_slider._name,
            initial_value=[start_date.isoformat(), stop_date.isoformat()],
            label=label,
            args={
                "start": 0,
                "stop": len(dates_list) - 1,
                "step": 1,
                "steps": [d.isoformat() for d in dates_list],
                "debounce": debounce,
                "orientation": orientation,
                "show-value": show_value,
                "full-width": full_width,
                "disabled": disabled,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> date_slider:
        """Create a date slider from a dataframe series.

        Args:
            series (DataFrameSeries): A pandas Series containing datetime values.
            **kwargs: Additional keyword arguments passed to the date slider constructor.
                Supported arguments: start, stop, step, label, and any other date slider parameters.

        Returns:
            date_slider: A date slider initialized with the series' min and max dates as bounds.
        """
        info = get_date_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return date_slider(start=start, stop=stop, label=label, **kwargs)

    def _find_closest_index(
        self, target_date: dt.date, dates_list: list[dt.date]
    ) -> int:
        """Find the index of the closest date in the list via binary search."""
        if not dates_list:
            raise ValueError("Empty dates list")

        closest_idx = 0
        min_diff = abs((target_date - dates_list[0]).days)

        for idx, date in enumerate(dates_list):
            diff = abs((target_date - date).days)
            if diff < min_diff:
                min_diff = diff
                closest_idx = idx
            elif diff > min_diff:
                # List is sorted, so we can stop early
                break

        return closest_idx

    @property
    def start(self) -> dt.date:
        """Get the minimum selectable date.

        Returns:
            datetime.date: The start date, which is either the user-specified minimum date
                or 01-01-0001 if no start date was specified.
        """
        return self._start

    @property
    def stop(self) -> dt.date:
        """Get the maximum selectable date.

        Returns:
            datetime.date: The stop date, which is either the user-specified maximum date
                or 12-31-9999 if no stop date was specified.
        """
        return self._stop

    @property
    def step(self) -> dt.timedelta:
        """Get the slider increment.

        Returns:
            datetime.timedelta: The step timedelta.
        """
        return self._step

    def _convert_value(self, value: list[str]) -> tuple[dt.date, dt.date]:
        return convert_str_to_date(value[0]), convert_str_to_date(value[1])
