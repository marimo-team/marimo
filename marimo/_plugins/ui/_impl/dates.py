# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime as dt
from typing import (
    Any,
    Callable,
    Final,
    Optional,
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
        # Catch different initialization formats
        if isinstance(value, dt.date):
            return value
        if isinstance(value, dt.datetime):
            return value.date()
        return dt.datetime.strptime(value, self.DATE_FORMAT).date()

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
        label: Optional[str] = None,
        on_change: Optional[Callable[[Optional[dt.datetime]], None]] = None,
        full_width: bool = False,
        disabled: bool = False,
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
            if start is None or stop is None:
                value = (dt.date.today(), dt.date.today())
            else:
                value = (start, stop)
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
        self, value: tuple[str, str] | tuple[dt.date, dt.date]
    ) -> tuple[dt.date, dt.date]:
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
