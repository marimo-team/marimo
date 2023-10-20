# Copyright 2023 Marimo. All rights reserved.
"""Interactive UI elements.

This module contains a library of interactive UI elements.
"""

__all__ = [
    "altair_chart",
    "array",
    "batch",
    "button",
    "checkbox",
    "date",
    "dataframe",
    "dictionary",
    "dropdown",
    "file",
    "form",
    "microphone",
    "multiselect",
    "number",
    "radio",
    "refresh",
    "slider",
    "switch",
    "table",
    "text_area",
    "text",
]


from marimo._plugins.ui._impl.altair_chart import altair_chart
from marimo._plugins.ui._impl.array import array
from marimo._plugins.ui._impl.batch import batch
from marimo._plugins.ui._impl.dataframes.dataframe import dataframe
from marimo._plugins.ui._impl.dictionary import dictionary
from marimo._plugins.ui._impl.input import (
    button,
    checkbox,
    date,
    dropdown,
    file,
    form,
    multiselect,
    number,
    radio,
    slider,
    text,
    text_area,
)
from marimo._plugins.ui._impl.microphone import microphone
from marimo._plugins.ui._impl.refresh import refresh
from marimo._plugins.ui._impl.switch import switch
from marimo._plugins.ui._impl.table import table
