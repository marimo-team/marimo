import marimo

__generated_with = "0.11.24"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import polars as pl
    import altair as alt
    return alt, mo, pd, pl


@app.cell
def _(mo):
    mo.md(r"""# Printing Rich Elements""")
    return


@app.cell
def _(alt, mo, pd):
    text = mo.ui.text(placeholder="Enter", on_change=lambda x: print("hi"))
    warn_btn = mo.ui.button(
        kind="warn", on_click=lambda x: print("button clicked!")
    )
    password = mo.ui.text(kind="password", value="secret")

    dictionary = mo.ui.dictionary(
        {
            "slider": mo.ui.slider(1, 10),
            "text": mo.ui.text(),
            "date": mo.ui.date(),
        }
    )


    def simple_echo_model(messages, config):
        return f"You said: {messages[-1].content}"


    chat = mo.ui.chat(
        simple_echo_model,
        prompts=["Hello", "How are you?"],
        show_configuration_controls=True,
    )

    img = mo.image(
        src="https://marimo.io/logo.png",
        alt="Marimo logo",
        width=100,
        height=100,
    )
    html_img = mo.Html(
        "<img src='https://marimo.io/logo.png' width='100px' height='100px' alt='Marimo logo'>"
    )

    office_characters = [
        {"first_name": "Michael", "last_name": "Scott"},
        {"first_name": "Jenna", "last_name": "Leigh"},
    ]
    table = mo.ui.table(office_characters)

    user_info = mo.md(
        """
        - What's your name?: {name}
        - When were you born?: {birthday}
        """
    ).batch(name=mo.ui.text(), birthday=mo.ui.date())

    source = pd.DataFrame(
        {
            "a": ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            "b": [28, 55, 43, 91, 81, 53, 19, 87, 52],
        }
    )

    chart = alt.Chart(source).mark_bar().encode(x="a", y="b")

    mermaid = mo.mermaid(
        "graph TD\n  A[Christmas] -->|Get money| B(Go shopping)\n  B --> C{Let me think}\n  C -->|One| D[Laptop]\n  C -->|Two| E[iPhone]\n  C -->|Three| F[Car]"
    )

    tabs = mo.ui.tabs(
        {
            "📈 Sales": chart,
            "📊 Chatbot": chat,
            "💻 Settings": mo.ui.text(placeholder="Key"),
        }
    )


    data = {
        "buttons": [mo.ui.button(kind="warn"), mo.ui.button(kind="invalid")],
        "mixed": [mo.ui.button(kind="info"), "apples"],
        "arrays": mo.ui.array([text] * 2),
        "dictionary": [dictionary, dictionary],
        "raw_objects": [
            {"fruits": ["apples", "bananas"]},
            {"trees": {"plants": "flowers"}},
        ],
        "raw_lists": [
            ["fruits", "trees", "animals"],
            ["humans", "aliens", "life"],
        ],
        "images": [img, html_img],
        "batch": user_info,
        "dropdowns": [
            mo.ui.dropdown(options=["apple", "bananas", "coconut"]),
            mo.ui.multiselect(options=["apple", "bananas", "coconut"]),
        ],
        "markdown": mo.md("## Inputs here"),
        "chat": chat,
        "file": mo.ui.file(),
        "table": table,
        "chart": mo.ui.altair_chart(chart),
        "mermaid": mermaid,
        "tabs": tabs,
    }

    mo.vstack([mo.md("## Dictionary"), data])
    return (
        chart,
        chat,
        data,
        dictionary,
        html_img,
        img,
        mermaid,
        office_characters,
        password,
        simple_echo_model,
        source,
        table,
        tabs,
        text,
        user_info,
        warn_btn,
    )


@app.cell
def _(data, mo):
    mo.vstack([mo.md("## Table"), mo.ui.table(data, page_size=20)])
    return


@app.cell
def _(data, mo, pd):
    pandas_rich = pd.DataFrame(data).transpose()
    mo.vstack([mo.md("## Pandas dataframe"), pandas_rich])
    return (pandas_rich,)


@app.cell
def _(mo, pandas_rich):
    mo.vstack([mo.md("## Table containing pandas df"), mo.ui.table(pandas_rich)])
    return


@app.cell
def _(data, mo, pl):
    data.pop("arrays", None)
    data.pop("batch", None)
    data.pop("mixed", None)

    pl_df = pl.DataFrame(data)
    mo.vstack([mo.md("## Polars dataframe"), pl_df])
    return (pl_df,)


@app.cell
def _(mo, password):
    mo.md(f"### Password value: {password.value}")
    return


@app.cell
def _(mo, pl_df):
    mo.vstack([mo.md("## Table containing polars dataframe"), mo.ui.table(pl_df)])
    return


@app.cell
def _(mo):
    mo.md(f"""
    ## This will crash the kernel (hence not enabled)

    `pl.DataFrame(data).transpose()`
    """)
    # pl.DataFrame(data).transpose()
    return


if __name__ == "__main__":
    app.run()
