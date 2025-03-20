# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui

HAS_PANDAS = DependencyManager.pandas.has()
HAS_NUMPY = DependencyManager.numpy.has()


def test_number_init() -> None:
    number = ui.number(1, 10)
    assert number.start == 1
    assert number.stop == 10
    assert number.step is None
    assert number.value == 1

    number = ui.number(1, 10, value=5)
    assert number.start == 1
    assert number.stop == 10
    assert number.step is None
    assert number.value == 5
    number._update(6)
    assert number.value == 6
    number._update(6.5)
    # unlike slider, number should not round because users can type
    # arbitrary numbers
    assert number.value == 6.5


def test_number_out_of_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.number(1, 10, value=11)

    assert "must be less than or equal" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.number(1, 10, value=0)

    assert "must be greater than or equal" in str(e.value)


def test_number_invalid_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.number(1, 0)

    assert "must be less than or equal to" in str(e.value)


def test_number_default_value() -> None:
    # Test default value when not specified
    number = ui.number(1, 10)
    assert number.value == 1

    # Test default value when only stop is specified
    number = ui.number(stop=10)
    assert number.value == 10

    # Test default value when neither start nor stop is specified
    number = ui.number()
    assert number.value is None

    # Test default value with step
    number = ui.number(1, 10, step=2)
    assert number.value == 1

    # Test that explicitly set value overrides default
    number = ui.number(1, 10, value=5)
    assert number.value == 5


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_number_from_dataframe() -> None:
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3]})
    number = ui.number.from_series(df["A"], step=0.1, label="Custom label")
    assert number.start == 1
    assert number.stop == 3
    assert number.value == 1
    assert number.step == 0.1
    assert number._args.label == "Custom label"


def test_slider_init() -> None:
    slider = ui.slider(1, 10)
    assert slider.start == 1
    assert slider.stop == 10
    assert slider.step is None
    assert slider.value == 1
    assert slider.steps is None

    slider = ui.slider(1, 10, value=5)
    assert slider.start == 1
    assert slider.stop == 10
    assert slider.step is None
    assert slider.value == 5
    assert slider.steps is None
    assert isinstance(slider.value, int)

    slider = ui.slider(1, 10, value=5.0)
    assert slider.value == 5.0
    assert isinstance(slider.value, float)

    slider._update(6)
    assert slider.value == 6.0
    assert isinstance(slider.value, float)

    slider = ui.slider(steps=[1, 3, 6], value=3)
    assert slider.start == 1
    assert slider.stop == 6
    assert slider.step is None
    assert slider.value == 3
    assert slider.steps == [1, 3, 6]

    # value not in steps, set to first value in steps
    slider = ui.slider(steps=[1, 3, 6], value=7)
    assert slider.value == 1


def test_slider_invalid_steps() -> None:
    """Tests for invalid steps"""
    # test for empty steps
    with pytest.raises(TypeError) as e:
        ui.slider(steps=[])

    assert "Invalid steps" in str(e.value)

    # test for non-numeric steps
    with pytest.raises(TypeError) as e:
        ui.slider(steps=[1, 4, "3"])

    assert "Invalid steps" in str(e.value)


def test_slider_invalid_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.slider(1, 0)

    assert "Invalid bounds" in str(e.value)


def test_slider_exclusive_args() -> None:
    with pytest.raises(ValueError) as e:
        ui.slider(start=1, steps=[1, 3, 6])

    assert "Invalid arguments" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.slider(step=2, start=3)

    assert "Missing arguments" in str(e.value)


def test_slider_out_of_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.slider(1, 10, value=11)

    assert "out of bounds" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.slider(1, 10, value=0)

    assert "out of bounds" in str(e.value)


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_slider_from_dataframe() -> None:
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3]})
    slider = ui.slider.from_series(df["A"], step=0.1, label="Custom label")
    assert slider.start == 1
    assert slider.stop == 3
    assert slider.value == 1
    assert slider.step == 0.1
    assert slider._args.label == "Custom label"


def test_range_slider_init() -> None:
    slider = ui.range_slider(1, 10)
    assert slider.start == 1
    assert slider.stop == 10
    assert slider.step is None
    assert slider.value == [1, 10]
    assert slider.steps is None

    slider = ui.range_slider(1, 10, value=[2, 5])
    assert slider.start == 1
    assert slider.stop == 10
    assert slider.step is None
    assert slider.value == [2, 5]
    assert slider.steps is None
    assert all(isinstance(num, int) for num in slider.value)

    slider = ui.range_slider(1, 10, value=[2.1, 5.1])
    assert slider.value == [2.1, 5.1]
    assert all(isinstance(num, float) for num in slider.value)

    slider._update([3, 6])
    assert slider.value == [3.0, 6.0]
    for num in slider.value:
        # initial value was a float, so ints should be
        # cast to floats
        assert isinstance(num, float)

    slider = ui.range_slider(steps=[1, 3, 6, 10, 17, 20], value=[3, 17])
    assert slider.start == 1
    assert slider.stop == 20
    assert slider.step is None
    assert slider.value == [3, 17]
    assert slider.steps == [1, 3, 6, 10, 17, 20]

    # value not in steps, set to first value in steps
    slider = ui.range_slider(steps=[1, 3, 6, 10, 17, 20], value=[7, 10])
    assert slider.value == [1, 20]


def test_range_slider_invalid_steps() -> None:
    """Tests for invalid steps"""
    # test for empty steps
    with pytest.raises(TypeError) as e:
        ui.range_slider(steps=[])

    assert "Invalid steps" in str(e.value)

    # test for non-numeric steps
    with pytest.raises(TypeError) as e:
        ui.range_slider(steps=[1, 4, "3"])

    assert "Invalid steps" in str(e.value)


def test_range_slider_invalid_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.range_slider(1, 0)

    assert "Invalid bounds" in str(e.value)


def test_range_slider_exclusive_args() -> None:
    with pytest.raises(ValueError) as e:
        ui.range_slider(start=1, steps=[1, 3, 6])

    assert "Invalid arguments" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.range_slider(step=2, start=3)

    assert "Missing arguments" in str(e.value)


def test_range_slider_out_of_bounds() -> None:
    with pytest.raises(ValueError) as e:
        ui.range_slider(1, 10, value=[1, 11])

    assert "out of bounds" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.range_slider(1, 10, value=[0, 10])

    assert "out of bounds" in str(e.value)


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_range_slider_from_dataframe() -> None:
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3]})
    slider = ui.range_slider.from_series(
        df["A"], step=0.1, label="Custom label"
    )
    assert slider.start == 1
    assert slider.stop == 3
    assert slider.value == [1, 3]
    assert slider.step == 0.1
    assert slider._args.label == "Custom label"


def test_text() -> None:
    assert ui.text().value == ""
    assert ui.text(value="hello world").value == "hello world"

    text = ui.text()
    text._update("value")
    assert text.value == "value"


def test_checkbox_init() -> None:
    assert not ui.checkbox().value
    assert ui.checkbox(value=True).value


def test_radio() -> None:
    radio = ui.radio(options=["1", "2", "3"], value="1")
    assert radio.value == "1"

    radio._update("2")
    assert radio.value == "2"

    radio = ui.radio(options={"1": 1, "2": 2, "3": 3}, value="1")
    assert radio.value == 1

    radio._update("2")
    assert radio.value == 2


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_radio_from_dataframe() -> None:
    import pandas as pd

    df = pd.DataFrame({"A": ["a", "b", "c"]})
    radio = ui.radio.from_series(df["A"], value="b")
    assert radio.options == {
        "a": "a",
        "b": "b",
        "c": "c",
    }
    assert radio.value == "b"


def test_dropdown() -> None:
    dd = ui.dropdown(options=["1", "2", "3"])
    assert dd.value is None

    dd._update(["2"])
    assert dd.value == "2"

    dd = ui.dropdown(options={"1": 1, "2": 2, "3": 3}, value="1")
    assert dd.value == 1

    dd._update(["2"])
    assert dd.value == 2


@dataclass
class SomeObject:
    a: int


def test_dropdown_with_non_string_options() -> None:
    # Integer options
    dd = ui.dropdown(options=[1, 2, 3], value=1)
    assert dd.options == {"1": 1, "2": 2, "3": 3}
    assert dd.value == 1

    dd._update(["2"])
    assert dd.value == 2

    # Float options
    dd = ui.dropdown(options=[1.0, 2.0, 3.0], value=1.0)
    assert dd.options == {"1.0": 1.0, "2.0": 2.0, "3.0": 3.0}
    assert dd.value == 1.0

    dd._update(["2.0"])
    assert dd.value == 2.0

    # Boolean options
    dd = ui.dropdown(options=[True, False], value=True)
    assert dd.options == {"True": True, "False": False}
    assert dd.value is True

    dd._update(["False"])
    assert dd.value is False

    # Rich objects
    dd = ui.dropdown(
        options=[SomeObject(a=1), SomeObject(a=2), SomeObject(a=3)],
        value=SomeObject(a=1),
    )
    assert dd.options == {
        "SomeObject(a=1)": SomeObject(a=1),
        "SomeObject(a=2)": SomeObject(a=2),
        "SomeObject(a=3)": SomeObject(a=3),
    }
    assert dd.value == SomeObject(a=1)

    dd._update(["SomeObject(a=2)"])
    assert dd.value == SomeObject(a=2)

    # Mixed types
    dd = ui.dropdown(
        options=[1, "2", SomeObject(a=3)],
        value="2",
    )
    assert dd.options == {"1": 1, "2": "2", "SomeObject(a=3)": SomeObject(a=3)}
    assert dd.value == "2"


def test_dropdown_too_many_options() -> None:
    with pytest.raises(ValueError) as e:
        ui.dropdown(options={str(i): i for i in range(2000)})

    assert "maximum number" in str(e.value)


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_dropdown_from_dataframe() -> None:
    import pandas as pd

    df = pd.DataFrame({"A": ["a", "b", "c"]})
    dd = ui.dropdown.from_series(df["A"], value="b")
    assert dd.options == {
        "a": "a",
        "b": "b",
        "c": "c",
    }
    assert dd.value == "b"


def test_multiselect() -> None:
    options_list = ["Apples", "Oranges", "Bananas"]
    ms = ui.multiselect(options=options_list)
    assert ms.value == []

    ms._update(["Apples"])
    assert ms.value == ["Apples"]

    ms._update(["Apples", "Oranges"])
    assert ms.value == ["Apples", "Oranges"]

    options_dict = {"Apples": 1, "Oranges": 2, "Bananas": 3}
    ms = ui.multiselect(options=options_dict, value=["Apples"])
    assert ms.value == [1]

    ms._update(["Apples", "Oranges", "Bananas"])
    assert ms.value == [1, 2, 3]

    ms = ui.multiselect(options=options_list, max_selections=2)
    assert ms.value == []

    ms._update(["Apples"])
    assert ms.value == ["Apples"]

    with pytest.raises(ValueError):
        ms = ui.multiselect(
            options=options_list, value=options_list, max_selections=0
        )

    with pytest.raises(ValueError):
        ms = ui.multiselect(
            options=options_list, value=options_list, max_selections=2
        )

    with pytest.raises(ValueError):
        ms = ui.multiselect(options=options_list, max_selections=-10)


def test_multiselect_non_string_options() -> None:
    # Integer options
    options_list = [1, 2, 3]
    ms = ui.multiselect(options=options_list)
    assert ms.options == {"1": 1, "2": 2, "3": 3}
    assert ms.value == []

    ms._update(["1"])
    assert ms.value == [1]

    ms._update(["1", "2"])
    assert ms.value == [1, 2]

    # Float options
    options_list = [1.0, 2.0, 3.0]
    ms = ui.multiselect(options=options_list, value=[1.0])
    assert ms.options == {"1.0": 1.0, "2.0": 2.0, "3.0": 3.0}
    assert ms.value == [1.0]

    # Boolean options
    options_list = [True, False]
    ms = ui.multiselect(options=options_list, value=[True])
    assert ms.options == {"True": True, "False": False}
    assert ms.value == [True]

    # Rich objects
    options_list = [SomeObject(a=1), SomeObject(a=2), SomeObject(a=3)]
    ms = ui.multiselect(options=options_list, value=[SomeObject(a=1)])
    assert ms.options == {
        "SomeObject(a=1)": SomeObject(a=1),
        "SomeObject(a=2)": SomeObject(a=2),
        "SomeObject(a=3)": SomeObject(a=3),
    }
    assert ms.value == [SomeObject(a=1)]

    ms._update(["SomeObject(a=2)"])
    assert ms.value == [SomeObject(a=2)]

    # Mixed types
    options_list = [1, "2", (3, 4)]
    ms = ui.multiselect(options=options_list, value=["1"])
    assert ms.options == {"1": 1, "2": "2", "(3, 4)": (3, 4)}
    assert ms.value == [1]

    ms._update(["1", "(3, 4)"])
    assert ms.value == [1, (3, 4)]


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_multiselect_from_series_non_string() -> None:
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3]})
    ms = ui.multiselect.from_series(df["A"], value=["2"])
    assert ms.options == {
        "1": 1,
        "2": 2,
        "3": 3,
    }
    assert ms.value == [2]


def test_multiselect_too_many_options() -> None:
    with pytest.raises(ValueError) as e:
        ui.multiselect(options={str(i): i for i in range(200000)})

    assert "maximum number" in str(e.value)


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_multiselect_from_dataframe() -> None:
    import pandas as pd

    df = pd.DataFrame({"A": ["a", "b", "c"]})
    ms = ui.multiselect.from_series(df["A"], value=["b"])
    assert ms.options == {
        "a": "a",
        "b": "b",
        "c": "c",
    }
    assert ms.value == ["b"]


def test_button() -> None:
    assert ui.button().value is None
    assert ui.button(value=1).value == 1

    # default callback does nothing
    button = ui.button(value=1)
    button._update(None)
    assert button.value == 1

    button = ui.button(on_click=lambda v: v + 1, value=0)
    assert button.value == 0
    button._update(None)
    assert button.value == 1
    button._update(None)
    assert button.value == 2


def test_on_change() -> None:
    state = []
    button = ui.checkbox(on_change=lambda v: state.append(v))
    assert not state
    button._update(False)
    assert state == [False]
    button._update(True)
    assert state == [False, True]


def test_form_in_array_retains_on_change() -> None:
    def on_change(*args: Any) -> None:
        del args
        ...

    array = ui.array([ui.form(ui.checkbox(), on_change=on_change)])
    assert array[0]._on_change == on_change


def test_form_in_dictionary_allowed() -> None:
    checkbox = ui.checkbox()
    form = checkbox.form()
    d = ui.dictionary({"form": form})
    assert checkbox._id != d["form"].element._id


def test_file_validation() -> None:
    """Test file type validation in the file class."""
    # Valid filetypes should be accepted
    ui.file(filetypes=[".csv", ".txt"])
    ui.file(filetypes=["audio/*"])
    ui.file(filetypes=["video/*"])
    ui.file(filetypes=["image/*"])
    ui.file(filetypes=["application/json"])
    ui.file(filetypes=["text/plain"])
    ui.file(filetypes=[".csv", "application/json"])  # Mixed types are allowed
    ui.file(filetypes=["text/html", "application/xml"])  # Multiple MIME types

    # Invalid filetypes should raise ValueError
    with pytest.raises(ValueError) as e:
        ui.file(filetypes=["csv"])
    assert "must start with a dot" in str(e.value)
    assert "or contain a forward slash" in str(e.value)
    assert "csv" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.file(filetypes=["txt", ".csv"])
    assert "must start with a dot" in str(e.value)
    assert "or contain a forward slash" in str(e.value)
    assert "txt" in str(e.value)

    with pytest.raises(ValueError) as e:
        ui.file(filetypes=["doc", "pdf"])
    assert "must start with a dot" in str(e.value)
    assert "or contain a forward slash" in str(e.value)
    assert "doc, pdf" in str(e.value)


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
def test_numpy_steps() -> None:
    import numpy as np

    steps = np.array([1, 2, 3, 4, 5])
    slider = ui.slider(steps=steps)
    assert slider.steps == [1, 2, 3, 4, 5]
    assert slider.start == 1
    assert slider.stop == 5
    assert slider.step is None

    range_slider = ui.range_slider(steps=steps)
    assert range_slider.steps == [1, 2, 3, 4, 5]
    assert range_slider.start == 1
    assert range_slider.stop == 5
    assert range_slider.step is None


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
def test_log_scale() -> None:
    import numpy as np

    steps = np.logspace(0, 3, 4)
    slider = ui.slider(steps=steps)

    assert slider.steps == [1, 10, 100, 1000]
    assert slider.start == 1
    assert slider.stop == 1000
    assert slider.step is None

    range_slider = ui.range_slider(steps=steps)
    assert range_slider.steps == [1, 10, 100, 1000]
    assert range_slider.start == 1
    assert range_slider.stop == 1000
    assert range_slider.step is None


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
def test_power_scale() -> None:
    import numpy as np

    steps = np.power([1, 2, 3], 2)
    slider = ui.slider(steps=steps)
    assert slider.steps == [1, 4, 9]
    assert slider.start == 1
    assert slider.stop == 9
    assert slider.step is None

    range_slider = ui.range_slider(steps=steps)
    assert range_slider.steps == [1, 4, 9]
    assert range_slider.start == 1
    assert range_slider.stop == 9
    assert range_slider.step is None
