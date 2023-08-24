import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("## Build a Superhero with Generative AI")
    return


@app.cell
def __(mo):
    openaikey = mo.ui.text(label="🤖 OpenAI Key", kind="password")
    config = mo.hstack([openaikey])
    mo.accordion({"⚙️ Enter your OpenAI key": config})
    return config, openaikey


@app.cell
def __(mo):
    item = mo.ui.text(label="Enter the name of an animal: ").form()
    item
    return item,


@app.cell
def __(item, mo):
    content = f"💬 Suggest three superhero names, given the following animal: {item.value}"

    mo.md(content) if item.value else None
    return content,


@app.cell
def __(content, item, mo, openai, openaikey):
    openai.api_key = openaikey.value

    result = None
    if item.value:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
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
    result = None
    if item.value:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
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
    return response, result


@app.cell
def __(mo, result):
    choices = result.split("\n") if result else []
    superhero = mo.ui.dropdown(choices)

    mo.md(
        f"""
        Choose a super hero: {superhero}
        """
    ) if result else None
    return choices, superhero


@app.cell
def __(mo, openai, superhero):
    catchphrase = None

    if superhero.value:
        catchphraseResponse = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
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
    return catchphrase, catchphraseResponse


@app.cell
def __(catchphrase, mo):
    generate_image_button = mo.ui.button(label="📷 Generate Image")
    generate_image_button if catchphrase else None
    return generate_image_button,


@app.cell
def __(generate_image_button, mo, openai, superhero):
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
    return res, url


@app.cell
def __():
    import marimo as mo
    import openai
    return mo, openai


if __name__ == "__main__":
    app.run()
