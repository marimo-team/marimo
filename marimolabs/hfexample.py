import marimo

__generated_with = "0.3.8"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimolabs as molabs
    return molabs,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    from dataclasses import asdict
    return asdict,


@app.cell
def __(mo):
    models = mo.ui.dropdown([
        "models/facebook/bart-large-mnli",
        "models/sentence-transformers/all-MiniLM-L6-v2",
    ], label="Choose a model")
    models
    return models,


@app.cell
def __(mo, models, molabs):
    mo.stop(models.value is None)

    model = molabs.huggingface.load(models.value)
    return model,


@app.cell
def __(model):
    model.examples
    return


@app.cell
def __(model):
    inputs = model.inputs
    inputs
    return inputs,


@app.cell
def __(inputs, mo, model):
    mo.stop(inputs.value is None, mo.md("Output not available: submit the model inputs 👆"))
    model.inference_function(inputs.value)
    return


@app.cell
def __(model):
    model.inference_function(model.examples[0])
    return


if __name__ == "__main__":
    app.run()
