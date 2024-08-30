# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime as dt
from typing import (
    Any,
    Callable,
    Final,
    Optional,
    Tuple,
    Union,
    cast,
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
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return date(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(self, value: str) -> dt.date:
        # Catch different initialization formats
        if isinstance(value, dt.date):
            return value
        if isinstance(value, dt.datetime):
            return value.date()
        return dt.datetime.strptime(value, self.DATE_FORMAT).date()

    @property
    def start(self) -> dt.date:
        return self._start

    @property
    def stop(self) -> dt.date:
        return self._stop


@mddoc
class datetime(UIElement[Optional[str], Optional[dt.datetime]]):
    """
    A datetime picker over an interval.

    **Example.**

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

    **Attributes.**

    - `value`: the selected datetime, possibly `None`
    - `start`: the minimum selectable datetime
    - `stop`: the maximum selectable datetime

    **Initialization Args.**

    - `start`: the minimum selectable datetime (default: minimum datetime)
    - `stop`: the maximum selectable datetime (default: maximum datetime)
    - `value`: default value
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of
      its container
    """

    _name: Final[str] = "marimo-datetime"
    DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S"

    def __init__(
        self,
        start: Optional[dt.datetime | str] = None,
        stop: Optional[dt.datetime | str] = None,
        value: Optional[dt.datetime | str] = None,
        *,
        label: Optional[str] = None,
        on_change: Optional[Callable[[Optional[dt.datetime]], None]] = None,
        full_width: bool = False,
    ):
        if isinstance(start, str):
            start = self._convert_value(start)
        if isinstance(stop, str):
            stop = self._convert_value(stop)
        if isinstance(value, str):
            value = self._convert_value(value)

        self._start = dt.datetime.min if start is None else start
        self._stop = dt.datetime.max if stop is None else stop

        if self._stop < self._start:
            raise ValueError(
                f"The stop datetime ({stop}) must be greater than "
                f"the start datetime ({start})"
            )

        if value is None:
            if start is None and stop is None:
                value = dt.datetime.today()
            elif start is not None:
                value = start
            else:
                value = stop
        value = cast(dt.datetime, value)

        if value < self._start or value > self._stop:
            raise ValueError(
                f"The default value ({value}) must be greater than "
                f"the start datetime ({start}) and less than the stop "
                f"datetime ({stop})."
            )

        super().__init__(
            component_name=datetime._name,
            initial_value=value.isoformat(timespec="seconds"),
            label=label,
            args={
                "start": self._start.strftime(self.DATETIME_FORMAT),
                "stop": self._stop.strftime(self.DATETIME_FORMAT),
                "full-width": full_width,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "datetime":
        """Create a datetime picker from a dataframe series."""
        info = get_datetime_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return datetime(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(self, value: Optional[str]) -> Optional[dt.datetime]:
        if value is None:
            return None
        POSSIBLE_FORMATS = [
            self.DATETIME_FORMAT,
            "%Y-%m-%d",
            "%Y-%m-%dT%H",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        for fmt in POSSIBLE_FORMATS:
            try:
                return dt.datetime.strptime(value, fmt)
            except ValueError:
                pass
        raise ValueError(f"Invalid datetime format: {value}")

    @property
    def start(self) -> dt.datetime:
        return self._start

    @property
    def stop(self) -> dt.datetime:
        return self._stop


@mddoc
class date_range(UIElement[Tuple[str, str], Tuple[dt.date, dt.date]]):
    """
    A date range picker over an interval.

    **Example.**

    ```python
    date_range = mo.ui.date_range(
        start=dt.date(2023, 1, 1), stop=dt.date(2023, 12, 31)
    )
    ```

    Or from a dataframe series:

    ```python
    date_range = mo.ui.date_range.from_series(df["date_column"])
    ```

    **Attributes.**

    - `value`: a tuple of two dates representing the selected range
    - `start`: the minimum selectable date
    - `stop`: the maximum selectable date

    **Initialization Args.**

    - `start`: the minimum selectable date (default: minimum date)
    - `stop`: the maximum selectable date (default: maximum date)
    - `value`: default value (tuple of two dates)
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    - `full_width`: whether the input should take up the full width of its
      container
    """

    _name: Final[str] = "marimo-date-range"
    DATEFORMAT: Final[str] = "%Y-%m-%d"

    def __init__(
        self,
        start: Optional[dt.date | str] = None,
        stop: Optional[dt.date | str] = None,
        value: Optional[Tuple[dt.date, dt.date] | Tuple[str, str]] = None,
        *,
        label: Optional[str] = None,
        on_change: Optional[Callable[[Tuple[dt.date, dt.date]], None]] = None,
        full_width: bool = False,
    ):
        if isinstance(start, str):
            start = self._convert_single_value(start)
        if isinstance(stop, str):
            stop = self._convert_single_value(stop)
        if value is not None:
            value = self._convert_value(value)

        self._start = dt.date(dt.MINYEAR, 1, 1) if start is None else start
        self._stop = dt.date(dt.MAXYEAR, 12, 31) if stop is None else stop

        if self._stop < self._start:
            raise ValueError(
                f"The stop date ({stop}) must be greater than "
                f"the start date ({start})"
            )

        if value is None:
            value = (dt.date.today(), dt.date.today())
        elif (
            value[0] < self._start
            or value[1] > self._stop
            or value[0] > value[1]
        ):
            raise ValueError(
                f"The default value ({value}) must be within "
                f"the range [{start}, {stop}] and the first date "
                f"must not be greater than the second date."
            )

        super().__init__(
            component_name=date_range._name,
            initial_value=(value[0].isoformat(), value[1].isoformat()),
            label=label,
            args={
                "start": self._start.isoformat(),
                "stop": self._stop.isoformat(),
                "full-width": full_width,
            },
            on_change=on_change,
        )

    @staticmethod
    def from_series(series: DataFrameSeries, **kwargs: Any) -> "date_range":
        """Create a date range picker from a dataframe series."""
        info = get_date_series_info(series)
        start = kwargs.pop("start", info.min)
        stop = kwargs.pop("stop", info.max)
        label = kwargs.pop("label", info.label)
        return date_range(start=start, stop=stop, label=label, **kwargs)

    def _convert_value(
        self, value: Tuple[str, str] | Tuple[dt.date, dt.date]
    ) -> Tuple[dt.date, dt.date]:
        return (
            self._convert_single_value(value[0]),
            self._convert_single_value(value[1]),
        )

    def _convert_single_value(self, value: str | dt.date) -> dt.date:
        if isinstance(value, dt.date):
            return value
        if isinstance(value, dt.datetime):
            return value.date()
        return dt.datetime.strptime(value, self.DATEFORMAT).date()

    @property
    def start(self) -> dt.date:
        return self._start

    @property
    def stop(self) -> dt.date:
        return self._stop
