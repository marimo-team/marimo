# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "requests==2.32.3",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    default_api_token = (
        mo.query_params().get("token") or mo.cli_args().get("token") or ""
    )
    api_token = mo.ui.text(
        label="API Token", value=default_api_token, kind="password"
    )
    return api_token, default_api_token


@app.cell
def _(api_token, default_api_token):
    api_token if not default_api_token else None
    api_token
    return


@app.cell(hide_code=True)
def _(mo):
    temperature = mo.ui.number(
        value=0.2, start=0, stop=1, step=0.05, label="Temperature"
    )
    top_p = mo.ui.number(value=0.7, start=0, stop=1, step=0.05, label="Top P")
    mo.accordion({"Settings": mo.hstack([temperature, top_p])})
    return temperature, top_p


@app.cell
def _(mo):
    uploaded_file = mo.ui.file(kind="area")
    uploaded_file
    return (uploaded_file,)


@app.cell
def _(mo, uploaded_file):
    import base64
    import io

    mo.stop(not uploaded_file.value)
    base64_encoded = base64.b64encode(uploaded_file.contents()).decode("utf-8")
    return (base64_encoded,)


@app.cell
def _(base64_encoded, mo):
    data_uri = f"data:image/png;base64,{base64_encoded}"
    mo.Html(f'<img src="{data_uri}" />')
    return (data_uri,)


@app.cell(hide_code=True)
def _(mo):
    prompt = mo.ui.text_area(
        label="Ask a question about the photo",
        full_width=True,
        placeholder="What is in this image?",
    ).form(bordered=False)
    prompt
    return (prompt,)


@app.cell
def _():
    import requests

    url = "https://ai.api.nvidia.com/v1/vlm/nvidia/neva-22b"
    return requests, url


@app.cell
def _(api_token, data_uri, mo, prompt, requests, temperature, top_p, url):
    mo.stop(not prompt.value)

    payload = {
        "messages": [
            {
                "content": f'{prompt.value} {data_uri}" />',
                "name": None,
                "role": "user",
            }
        ],
        "temperature": temperature.value,
        "top_p": top_p.value,
        "max_tokens": 1024,
        "seed": 42,
        "stream": False,
    }

    headers = {
        "authorization": f"Bearer {api_token.value}",
        "accept": "application/json",
        "content-type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers)
    res = response.json()
    return (res,)


@app.cell
def _(mo, res):
    try:
        content = res["choices"][0]["message"]["content"]
    except:
        content = res

    mo.md(f"**Response:** \n{res}")
    return


if __name__ == "__main__":
    app.run()
