import marimo

__generated_with = "0.1.5"
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
    mo.md(f"_Which predicted span do you prefer: model A or model B?._")
    return


@app.cell
def __(index, mo, next_button, previous_button):
    mo.hstack([index, previous_button, next_button], justify="start")
    return


@app.cell
def __(mo):
    mo.md("**Choose the better model.**").center()
    return


@app.cell
def __(mo):
    mo.hstack(
        [
            mo.md(
                """
                <span style='text-decoration: underline; text-decoration-color: red; text-decoration-thickness:3px'>Model A</span>
                """
            ),
            mo.md(
                """
                <span style='text-decoration: underline; text-decoration-color: blue; text-decoration-thickness:3px'>Model B</span>
                """
            ),
        ],
        justify="space-around",
    )
    return


@app.cell
def __(choices, mo):
    get_choices, set_choices = mo.state([choice for choice in choices])
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
def __(CHOICES_PATH, get_choices, index, mo, write_choices):
    preference = get_choices()[index.value]
    mo.stop(preference is None, mo.md("Choose your preference.").callout("warn"))
    write_choices(get_choices(), CHOICES_PATH)

    mo.md(f"You prefer model {preference}!").callout(
        kind="info" if preference == "B" else "danger"
    )
    return preference,


@app.cell
def __(PARAGRAPHS, SPANS, annotate, index, mo):
    mo.md(
        annotate(
            PARAGRAPHS[index.value],
            SPANS[index.value][0],
            SPANS[index.value][1],
        )
    ).callout()
    return


@app.cell
def __(PARAGRAPHS, SPANS, index, mo):
    mo.tabs({
        "Model A": PARAGRAPHS[index.value][
            SPANS[index.value][0][0] : SPANS[index.value][0][1]
        ],
        "Model B": PARAGRAPHS[index.value][
            SPANS[index.value][1][0] : SPANS[index.value][1][1]
        ]
    })
    return


@app.cell
def __(CHOICES_PATH, NUMBER_OF_EXAMPLES, load_choices):
    choices = load_choices(CHOICES_PATH, NUMBER_OF_EXAMPLES)
    return choices,


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
        first = [random.randint(0, len(text) - 1)]
        first.append(random.randint(first[0], len(text) - 1))
        second = [random.randint(0, len(text) - 1)]
        second.append(random.randint(second[0], len(text) - 1))

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
    def annotate(text, first_span, second_span):
        red_span = "<span style='text-decoration: underline 3px red'>"
        resolved_span = [second_span[0], second_span[1]]
        if resolved_span[0] > first_span[0] and resolved_span[0] < first_span[1]:
            resolved_span[0] += len(red_span)
        elif resolved_span[0] >= first_span[1]:
            resolved_span[0] += len(red_span) + len("</span>")

        if resolved_span[1] > first_span[0] and resolved_span[1] < first_span[1]:
            resolved_span[1] += len(red_span)
        elif resolved_span[1] >= first_span[1]:
            resolved_span[1] += len(red_span) + len("</span>")

        text = (
            text[: first_span[0]]
            + red_span
            + text[first_span[0] : first_span[1]]
            + "</span>"
            + text[first_span[1] :]
        )

        blue_span = "<span style='text-decoration: underline 3px blue'>"
        return (
            text[: resolved_span[0]]
            + blue_span
            + text[resolved_span[0] : resolved_span[1]]
            + "</span>"
            + text[resolved_span[1] :]
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
