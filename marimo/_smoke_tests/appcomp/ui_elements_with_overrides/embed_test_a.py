import marimo

__generated_with = "0.19.2"
app = marimo.App(width="full")


@app.cell
def _():
    # https://github.com/marimo-team/marimo/issues/7685
    import marimo as mo
    return


@app.cell
def _():
    import embed_test_b
    return (embed_test_b,)


@app.cell
def _(embed_test_b):
    clone_a = embed_test_b.app.clone()
    return (clone_a,)


@app.cell
async def _(clone_a):
    embed_a = await clone_a.embed()
    embed_a.output
    return (embed_a,)


@app.cell
def _(embed_test_b):
    clone_b = embed_test_b.app.clone()
    return (clone_b,)


@app.cell
async def _(clone_b, embed_a):
    (
        await clone_b.embed(
            defs={"value": embed_a.defs["value"], "label": "their", "kind": "warn"}
        )
    ).output
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
