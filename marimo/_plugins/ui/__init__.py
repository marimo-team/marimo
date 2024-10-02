# Copyright 2024 Marimo. All rights reserved.
"""Interactive UI elements.

This module contains a library of interactive UI elements.
"""

from __future__ import annotations

__all__ = [
    "altair_chart",
    "anywidget",
    "array",
    "batch",
    "button",
    "chat",
    "checkbox",
    "code_editor",
    "data_explorer",
    "dataframe",
    "date_range",
    "date",
    "datetime",
    "dictionary",
    "dropdown",
    "file_browser",
    "file",
    "form",
    "microphone",
    "multiselect",
    "number",
    "plotly",
    "radio",
    "range_slider",
    "refresh",
    "run_button",
    "slider",
    "switch",
    "table",
    "tabs",
    "text_area",
    "text",
]

from marimo._plugins.ui._impl.altair_chart import altair_chart
from marimo._plugins.ui._impl.array import array
from marimo._plugins.ui._impl.batch import batch
from marimo._plugins.ui._impl.chat.chat import chat
from marimo._plugins.ui._impl.data_explorer import data_explorer
from marimo._plugins.ui._impl.dataframes.dataframe import dataframe
from marimo._plugins.ui._impl.dates import (
    date,
    date_range,
    datetime,
)
from marimo._plugins.ui._impl.dictionary import dictionary
from marimo._plugins.ui._impl.from_anywidget import anywidget
from marimo._plugins.ui._impl.input import (
    button,
    checkbox,
    code_editor,
    dropdown,
    file,
    file_browser,
    form,
    multiselect,
    number,
    radio,
    range_slider,
    slider,
    text,
    text_area,
)
from marimo._plugins.ui._impl.microphone import microphone
from marimo._plugins.ui._impl.plotly import plotly
from marimo._plugins.ui._impl.refresh import refresh
from marimo._plugins.ui._impl.run_button import run_button
from marimo._plugins.ui._impl.switch import switch
from marimo._plugins.ui._impl.table import table
from marimo._plugins.ui._impl.tabs import tabs
