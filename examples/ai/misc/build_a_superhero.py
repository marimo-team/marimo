# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "openai==1.47.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Build a Superhero with Generative AI
    """)
    return


@app.cell
def _(mo):
    openaikey = mo.ui.text(label="🤖 OpenAI Key", kind="password")
    config = mo.hstack([openaikey])

    mo.accordion({"⚙️ Enter your OpenAI key": config})
    return (openaikey,)


@app.cell
def _(mo):
    item = mo.ui.text(label="Enter the name of an animal: ").form()
    item
    return (item,)


@app.cell
def _(item, mo):
    content = f"💬 Suggest three superhero names, given the following animal: {item.value}"

    mo.md(content) if item.value else None
    return (content,)


@app.cell
def _(content, item, mo, openai, openaikey):
    openai.api_key = openaikey.value

    result = None
    if item.value:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative assistant. Your responses should use newlines.",
                },
                {"role": "user", "content": content},
            ],
        )

        result = response.choices[0].message.content

    mo.md(
        f"""
        🤖 Response:

        {result}
        """
    ) if item.value else None
    return (result,)


@app.cell
def _(mo, result):
    choices = result.split("\n") if result else []
    superhero = mo.ui.dropdown(choices)

    mo.md(
        f"""
        Choose a superhero: {superhero}
        """
    ) if result else None
    return (superhero,)


@app.cell
def _(mo, openai, superhero):
    catchphrase = None

    if superhero.value:
        catchphraseResponse = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a creative assistant."},
                {
                    "role": "user",
                    "content": f"Create a catchphrase for {superhero.value}",
                },
            ],
        )

        catchphrase = catchphraseResponse.choices[0].message.content

    mo.md(
        f"""
        💬 Create a catchphrase for {superhero.value}

        🤖 Response:

        {catchphrase}
        """
    ) if superhero.value else None
    return (catchphrase,)


@app.cell
def _(catchphrase, mo):
    generate_image_button = mo.ui.button(label="📷 Generate Image")
    generate_image_button if catchphrase else None
    return (generate_image_button,)


@app.cell
def _(generate_image_button, mo, openai, superhero):
    generate_image_button

    url = None
    if superhero.value:
        res = openai.Image.create(
            prompt=superhero.value,
            n=1,
            size="256x256",
        )
        url = res["data"][0]["url"]

    mo.image(src=url) if url else None
    return


@app.cell
def _():
    import marimo as mo
    import openai

    return mo, openai


if __name__ == "__main__":
    app.run()
