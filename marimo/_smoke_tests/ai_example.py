import marimo

__generated_with = "0.8.19"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.md(r"""# Custom chatbots""")
    return


@app.cell
def __(mo):
    # Initialize a client
    import os

    mo.stop(
        "OPENAI_API_KEY" not in os.environ,
        "Please set the OPENAI_API_KEY environment variable",
    )

    import ell
    import openai

    # Create an openai client
    client = openai.Client(api_key=os.environ["OPENAI_API_KEY"])
    return client, ell, openai, os


@app.cell
def __():
    # Grab a dataset, we will use the cars dataset

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


    def my_model(messages, config):
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
    return BaseModel, Field, PromptsResponse, get_sample_prompts, my_model


@app.cell
def __(cars, get_sample_prompts, mo, my_model):
    prompts = get_sample_prompts(cars).parsed.prompts
    mo.ai.chat(
        model=my_model,
        prompts=prompts,
    )
    return (prompts,)


@app.cell
def __(mo):
    mo.md(r"""# Built-in chatbots""")
    return


@app.cell
def __(mo):
    a = mo.ai.chat(
        model=mo.ai.models.openai("gpt-4-turbo"),
        show_configuration_controls=True,
    )
    return (a,)


@app.cell
def __(mo):
    mo.ai.chat(
        model=mo.ai.models.openai("gpt-4-turbo"),
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


if __name__ == "__main__":
    app.run()
