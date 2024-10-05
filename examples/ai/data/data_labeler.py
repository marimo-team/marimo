import marimo

__generated_with = "0.1.4"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Data Labeler")
    return


@app.cell
def __(NUMBER_OF_EXAMPLES, mo):
    get_index, set_index = mo.state(0)


    def increment_index():
        set_index(lambda v: min(v + 1, NUMBER_OF_EXAMPLES - 1))


    def decrement_index() -> int:
        set_index(lambda v: max(0, v - 1))
    return decrement_index, get_index, increment_index, set_index


@app.cell
def __(decrement_index, increment_index, mo):
    next_button = mo.ui.button(label="next", on_change=lambda _: increment_index())

    previous_button = mo.ui.button(
        label="previous", on_change=lambda _: decrement_index()
    )
    return next_button, previous_button


@app.cell
def __(mo):
    mo.md(f"**Choose an example to label.**")
    return


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
def __(index, mo, next_button, previous_button):
    mo.hstack([index, previous_button, next_button], justify="start")
    return


@app.cell
def __(index, mo):
    mo.md(f"![img](https://picsum.photos/id/{index.value}/700/400)").center()
    return


@app.cell
def __(mo):
    mo.md("### Real or AI generated?").center()
    return


@app.cell
def __(LABELS_PATH, NUMBER_OF_EXAMPLES, load_labels):
    labels = load_labels(LABELS_PATH, NUMBER_OF_EXAMPLES)
    return labels,


@app.cell
def __(LABELS_PATH, labels, write_labels):
    def update_label(value, index):
        labels[index]["label"] = value
        write_labels(labels, LABELS_PATH)
    return update_label,


@app.cell
def __(LABELS_PATH, labels, write_labels):
    def update_notes(value, index):
        labels[index]["notes"] = value
        write_labels(labels, LABELS_PATH)
    return update_notes,


@app.cell
def __(mo, notes):
    mo.stop(len(notes.value) <= 100)

    _character_count = mo.md(f"`{len(notes.value)}/100` characters used").right()

    mo.md(
        f"""
        Notes can't be longer than 100 characters. {_character_count}
        """
    ).callout(kind="alert")
    return


@app.cell
def __(index, labels, mo, update_label, update_notes):
    data = labels[index.value]

    label_picker = mo.ui.radio(
        ["Real", "AI Generated", "Unlabeled"],
        value=data["label"],
        label="**Selection.**",
        on_change=lambda v: update_label(v, index.value),
    )

    notes = mo.ui.text_area(
        value=data["notes"],
        label="**Notes.**",
        on_change=lambda v: update_notes(v, index.value),
    )

    mo.hstack([label_picker, notes], justify="space-around")
    return data, label_picker, notes


@app.cell
def __(json, os):
    def load_labels(path, number_of_examples):
        if not os.path.exists(path):
            return [
                {"label": "Unlabeled", "notes": ""}
                for _ in range(number_of_examples)
            ]

        with open(path, "r") as f:
            labels = json.loads(f.read())
        assert len(labels) == number_of_examples
        return labels


    def write_labels(labels, path):
        # Trunacate notes
        labels = [
            {"label": item["label"], "notes": item["notes"][:100]}
            for item in labels
        ]
        with open(path, "w") as f:
            f.write(json.dumps(labels))
    return load_labels, write_labels


@app.cell
def __():
    NUMBER_OF_EXAMPLES = 100
    return NUMBER_OF_EXAMPLES,


@app.cell
def __():
    LABELS_PATH = "labels.json"
    return LABELS_PATH,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import json
    import os
    return json, os


if __name__ == "__main__":
    app.run()
