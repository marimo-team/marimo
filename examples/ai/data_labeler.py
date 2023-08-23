import marimo

__generated_with = "0.1.2"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Data Labeler")
    return


@app.cell
def __(NUMBER_OF_EXAMPLES, mo):
    index = mo.ui.number(0, NUMBER_OF_EXAMPLES, step=1)

    mo.md(f"**Choose an example to label.** {index}")
    return index,


@app.cell
def __(index, mo):
    mo.md(f"![img](https://picsum.photos/id/{index.value}/700/400)").center()
    return


@app.cell
def __(mo):
    mo.md("### Real or AI generated?").center()
    return


@app.cell
def __(index, labels, mo):
    data = labels[index.value]

    label_picker = mo.ui.radio(
        ["Real", "AI Generated", "Unlabeled"],
        value=data["label"],
        label="**Selection.**",
    )

    notes = mo.ui.text_area(value=data["notes"], label="**Notes.**")

    mo.hstack([label_picker, notes], justify="space-around")
    return data, label_picker, notes


@app.cell
def __(LABELS_PATH, index, label_picker, labels, notes, write_labels):
    labels[index.value] = {"label": label_picker.value, "notes": notes.value}
    write_labels(labels, LABELS_PATH)
    return


@app.cell
def __(LABELS_PATH, NUMBER_OF_EXAMPLES, load_labels):
    labels = load_labels(LABELS_PATH, NUMBER_OF_EXAMPLES)
    return labels,


@app.cell
def __(json, os):
    def load_labels(path, number_of_examples):
        if not os.path.exists(path):
            return [
                {"label": "Unlabeled", "labels": ""}
                for _ in range(number_of_examples)
            ]

        with open(path, "r") as f:
            labels = json.loads(f.read())
        assert len(labels) == number_of_examples
        return labels


    def write_labels(labels, path):
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
