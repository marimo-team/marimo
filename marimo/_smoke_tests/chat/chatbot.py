# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "ell-ai==0.0.12",
#     "marimo",
#     "openai==1.50.1",
#     "pydantic==2.9.2",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.8.20"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.md(r"""# Built-in chatbots""")
    return


@app.cell
def __(mo):
    mo.md(r"""## OpenAI""")
    return


@app.cell
def __(mo):
    mo.ui.chat(
        mo.ai.llm.openai(
            "gpt-4-turbo", system_message="You are a helpful data scientist"
        ),
        show_configuration_controls=True,
        prompts=[
            "Tell me a joke",
            "What is the meaning of life?",
            "What is 2 + {{number}}",
        ],
    )
    return


@app.cell
def __(mo):
    mo.md(r"""## Anthropic""")
    return


@app.cell
def __(mo):
    mo.ui.chat(
        mo.ai.llm.anthropic("claude-3-5-sonnet-20240620"),
        show_configuration_controls=True,
        prompts=[
            "Tell me a joke",
            "What is the meaning of life?",
            "What is 2 + {{number}}",
        ],
    )
    return


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    mo.md(r"""# Custom chatbots""")
    return


@app.cell(hide_code=True)
def __(mo):
    import os

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(label="OpenAI API key", kind="password")
    input_key if not os_key else None
    return input_key, os, os_key


@app.cell
def __(input_key, os_key):
    openai_key = os_key or input_key.value
    return (openai_key,)


@app.cell(hide_code=True)
def __(mo, openai_key):
    # Initialize a client
    mo.stop(
        not openai_key,
        "Please set the OPENAI_API_KEY environment variable or provide it in the input field",
    )

    import ell
    import openai

    # Create an openai client
    client = openai.Client(api_key=openai_key)
    return client, ell, openai


@app.cell
def __(mo):
    mo.md(r"""## Simple""")
    return


@app.cell
def __(client, ell, mo):
    @ell.simple("gpt-4o-mini-2024-07-18", client=client)
    def _my_model(prompt):
        """You are an annoying little brother, whatever I say, be sassy with your response"""
        return prompt


    mo.ui.chat(mo.ai.llm.simple(_my_model))
    return


@app.cell
def __(mo):
    mo.md(r"""## Complex""")
    return


@app.cell
def __():
    # Grab a dataset for the chatbot conversation, we will use the cars dataset

    from vega_datasets import data

    cars = data.cars()
    return cars, data


@app.cell
def __(cars, client, ell):
    from pydantic import BaseModel, Field


    class PromptsResponse(BaseModel):
        prompts: list[str] = Field(
            description="A list of prompts to use for the chatbot"
        )


    @ell.complex(
        "gpt-4o-mini-2024-07-18", client=client, response_format=PromptsResponse
    )
    def get_sample_prompts(df):
        """You are a helpful data scientist"""
        return (
            "Given the following schema of this dataset, "
            f"what would be three interesting questions to ask? \n{df.dtypes}"
        )


    def my_complex_model(messages, config):
        schema = cars.dtypes

        # This doesn't need to be ell or any model provider
        # You can use your own model here.
        @ell.complex(model="gpt-4o", temperature=0.7)
        def chat_bot(message_history):
            return [
                ell.system(f"""
                You are a helpful data scientist chatbot.

                I would like you to analyze this dataset. You must only ask follow-up questions or return a single valid JSON of a vega-lite specification so that it can be charted.

                Here is the dataset schema {schema}.

                If you are returning JSON, only return the json without any explanation. And don't wrap in backquotes or code fences
                """),
            ] + message_history

        # History
        message_history = [
            ell.user(message.content)
            if message.role == "user"
            else ell.assistant(message.content)
            for message in messages
        ]
        # Prompt
        # message_history.append(ell.user(prompt))

        # Go!
        response = chat_bot(message_history).text
        if response.startswith("{"):
            import altair as alt
            import json

            as_dict = json.loads(response)
            # add our cars dataset
            print(as_dict)
            as_dict["data"] = {"values": cars.dropna().to_dict(orient="records")}
            if "datasets" in as_dict:
                del as_dict["datasets"]
            return alt.Chart.from_dict(as_dict)
        return response
    return (
        BaseModel,
        Field,
        PromptsResponse,
        get_sample_prompts,
        my_complex_model,
    )


@app.cell
def __(cars, get_sample_prompts, mo, my_complex_model):
    prompts = get_sample_prompts(cars).parsed.prompts
    mo.ui.chat(
        my_complex_model,
        prompts=prompts,
    )
    return (prompts,)


if __name__ == "__main__":
    app.run()
