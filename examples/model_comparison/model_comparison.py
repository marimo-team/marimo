import marimo

__generated_with = "0.1.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Model Comparison")
    return


@app.cell
def __(NUMBER_OF_EXAMPLES, mo):
    get_index, set_index = mo.state(0)


    def increment_index():
        set_index(lambda v: min(v + 1, NUMBER_OF_EXAMPLES - 1))


    def decrement_index() -> int:
        set_index(lambda v: max(0, v - 1))

    next_button = mo.ui.button(label="next", on_change=lambda _: increment_index())
    previous_button = mo.ui.button(
        label="previous", on_change=lambda _: decrement_index()
    )
    return (
        decrement_index,
        get_index,
        increment_index,
        next_button,
        previous_button,
        set_index,
    )


@app.cell
def __(NUMBER_OF_EXAMPLES, get_index, mo, set_index):
    index = mo.ui.number(
        0,
        NUMBER_OF_EXAMPLES - 1,
        value=get_index(),
        step=1,
        debounce=True,
        label="example number",
        on_change=set_index,
    )
    return index,


@app.cell
def __(mo):
    mo.md(f"_Models A and B both predict spans. Which do you prefer?_")
    return


@app.cell
def __(NUMBER_OF_EXAMPLES, mo, num_a_preferred, num_b_preferred):
    mo.ui.table(
        [
            {"Model": "A", "Score": f"{num_a_preferred}/{NUMBER_OF_EXAMPLES}"},
            {"Model": "B", "Score": f"{num_b_preferred}/{NUMBER_OF_EXAMPLES}"},
        ],
        selection=None,
    )
    return


@app.cell
def __(index, mo, next_button, previous_button):
    mo.hstack([index, previous_button, next_button], justify="center")
    return


@app.cell
def __(CHOICES_PATH, get_choices, index, mo, write_choices):
    preference = get_choices()[index.value]
    mo.stop(preference is None, mo.md("**Choose the better model**.").center())
    write_choices(get_choices(), CHOICES_PATH)
    mo.md(f"You prefer **model {preference}**.").center()
    return preference,


@app.cell
def __(annotate, mo):
    mo.hstack(
        [
            mo.md(annotate("Model A", [0, len("Model A")], "yellow")),
            mo.md(annotate("Model B", [0, len("Model B")], "lightblue")),
        ],
        justify="space-around",
    )
    return


@app.cell
def __(CHOICES_PATH, PARAGRAPHS, load_choices, mo):
    get_choices, set_choices = mo.state(
        load_choices(CHOICES_PATH, len(PARAGRAPHS))
    )
    return get_choices, set_choices


@app.cell
def __(index, mo, set_choices):
    model_A = mo.ui.button(
        label="Model A",
        on_change=lambda _: set_choices(
            lambda v: v[: index.value] + ["A"] + v[index.value + 1 :]
        ),
    )

    model_B = mo.ui.button(
        label="Model B",
        on_change=lambda _: set_choices(
            lambda v: v[: index.value] + ["B"] + v[index.value + 1 :]
        ),
    )
    mo.hstack([model_A, model_B], justify="space-around")
    return model_A, model_B


@app.cell
def __(PARAGRAPHS, SPANS, annotate, index, mo):
    model_A_prediction = mo.md(
        annotate(
            PARAGRAPHS[index.value],
            SPANS[index.value][0],
            color="yellow"
        )
    )

    model_B_prediction = mo.md(
        annotate(
            PARAGRAPHS[index.value],
            SPANS[index.value][1],
            color="lightblue"
        )
    )
    return model_A_prediction, model_B_prediction


@app.cell
def __(mo, model_A_prediction, model_B_prediction):
    mo.hstack(
        [model_A_prediction, model_B_prediction], gap=2, justify="space-around"
    )
    return


@app.cell
def __(get_choices):
    num_a_preferred = sum(1 for c in get_choices() if c == "A")
    num_b_preferred = sum(1 for c in get_choices() if c == "B")
    return num_a_preferred, num_b_preferred


@app.cell
def __():
    CHOICES_PATH = "choices.json"
    return CHOICES_PATH,


@app.cell
def __(json, os):
    def load_choices(path, number_of_examples):
        if not os.path.exists(path):
            return [
                None
                for _ in range(number_of_examples)
            ]

        with open(path, "r") as f:
            choices = json.loads(f.read())
        assert len(choices) == number_of_examples
        return choices


    def write_choices(choices, path):
        # Trunacate notes
        with open(path, "w") as f:
            f.write(json.dumps(choices))
    return load_choices, write_choices


@app.cell
def __(PARAGRAPHS, random):
    random.seed(0)


    def predict_spans(text):
        first = [random.randint(0, len(text) - 2)]
        first.append(random.randint(first[0] + 1, len(text) - 1))
        second = [random.randint(0, len(text) - 2)]
        second.append(random.randint(second[0] + 1, len(text) - 1))

        return first, second

    SPANS = [predict_spans(p) for p in PARAGRAPHS]
    return SPANS, predict_spans


@app.cell
def __(HAMLET, textwrap):
    PARAGRAPHS = [
        textwrap.dedent(block).strip()[:1000]
        for block in HAMLET.split("\n\n")
        if block
    ]
    return PARAGRAPHS,


@app.cell
def __():
    def annotate(text, span, color):
        mark_start = f"<mark style='background-color:{color}'>"
        return (
            text[: span[0]]
            + mark_start
            + text[span[0] : span[1]]
            + "</mark>"
            + text[span[1] :]
        )
    return annotate,


@app.cell
def __(PARAGRAPHS):
    NUMBER_OF_EXAMPLES = len(PARAGRAPHS)
    return NUMBER_OF_EXAMPLES,


@app.cell
def __(urllib):
    _hamlet_url = "https://gist.githubusercontent.com/provpup/2fc41686eab7400b796b/raw/b575bd01a58494dfddc1d6429ef0167e709abf9b/hamlet.txt"

    with urllib.request.urlopen(_hamlet_url) as f:
        HAMLET = f.read().decode('utf-8')
    return HAMLET, f


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import json
    import os
    import random
    import textwrap
    import urllib
    return json, os, random, textwrap, urllib


if __name__ == "__main__":
    app.run()
