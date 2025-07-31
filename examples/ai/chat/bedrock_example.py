# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "litellm",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    # AWS Bedrock Chat Example

    This example demonstrates using AWS Bedrock with marimo's chat interface.

    AWS Bedrock provides access to foundation models from leading AI companies like Anthropic, Meta, and others.

    ⚠️ **Note:** You'll need an AWS account with access to the AWS Bedrock service and the specific model you want to use.
    """
    )
    return


@app.cell(hide_code=True)
def _():
    import os
    import boto3


    # For this example, let's add a helper to check AWS configuration
    def check_aws_config():
        """Check if AWS configuration is available"""
        # Check for credentials
        has_creds = False
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials:
                has_creds = True
        except:
            pass

        return {"has_credentials": has_creds}


    # Run the check
    aws_config = check_aws_config()
    return (aws_config,)


@app.cell
def _(aws_config, mo):
    # Display AWS configuration status
    mo.stop(
        not aws_config["has_credentials"],
        mo.md("""
            ### ⚠️ AWS Credentials Not Found

            To use AWS Bedrock, you need AWS credentials configured.
            Options:
            1. Set environment variables:
            ```
            export AWS_ACCESS_KEY_ID=your_key
            export AWS_SECRET_ACCESS_KEY=your_secret
            ```

            2. Configure AWS CLI:
            ```
            aws configure
            ```

            3. Use an AWS profile in ~/.aws/credentials
        """),
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # UI for model configuration

    # Predefined model options
    model_options = [
        "bedrock/us.amazon.nova-pro-v1:0",
        "bedrock/anthropic.claude-3-sonnet-20240229",
        "bedrock/anthropic.claude-3-haiku-20240307",
        "bedrock/meta.llama3-8b-instruct-v1:0",
        "bedrock/amazon.titan-text-express-v1",
        "bedrock/cohere.command-r-plus-v1",
    ]

    # Region options
    region_options = [
        "us-east-1",
        "us-west-2",
        "eu-central-1",
        "ap-northeast-1",
        "ap-southeast-1",
    ]

    # Model selection
    model = mo.ui.dropdown(
        options=model_options, value=model_options[0], label="AWS Bedrock Model"
    )

    # Region selection
    region = mo.ui.dropdown(
        options=region_options, value="us-east-1", label="AWS Region"
    )

    # Optional profile name
    profile = mo.ui.text(
        value="",
        label="AWS Profile (optional)",
        placeholder="Leave empty to use default credentials",
    )

    # System message
    system_message = mo.ui.text_area(
        value="You are a helpful, harmless assistant. Provide clear, concise answers.",
        label="System Message",
        rows=2,
    )

    # Create a form to wrap all inputs
    config_form = (
        mo.md("""
            AWS Bedrock Chat Configuration:
            {model}
            {region}
            {profile}
            {system_message}
        """)
        .batch(
            model=model,
            region=region,
            profile=profile,
            system_message=system_message,
        )
        .form(
            submit_button_label="Update Chat Configuration",
        )
    )

    config_form
    return (config_form,)


@app.cell
def _(mo):
    mo.md(r"""## AWS Bedrock Chat""")
    return


@app.cell
def _(config_form, max_tokens, mo, temperature):
    # Create a refreshable chat component that updates when the form is submitted
    def create_chat(config_form):
        # temperature = config_form.value["temperature"]
        # max_tokens = config_form.value["max_tokens"]
        model = config_form.value["model"]
        region = config_form.value["region"]
        system_message = config_form.value["system_message"]
        profile = config_form.value["profile"]
        try:
            # Create chat config
            chat_config = mo.ai.ChatModelConfig(
                temperature=temperature,
                max_tokens=max_tokens,
                # top_k=1,
                # top_p=1.0,
                # frequency_penalty=1,
                # presence_penalty=1,
            )

            # Create model with optional profile
            model_kwargs = {
                "model": model,
                "region_name": region,
                "system_message": system_message,
            }

            # Add profile if specified
            if profile.strip():
                model_kwargs["profile_name"] = profile.strip()

            # Create chat interface
            chatbot = mo.ui.chat(
                mo.ai.llm.bedrock(**model_kwargs),
                allow_attachments=[
                    "image/png",
                    "image/jpeg",
                ],
                prompts=[
                    "Hello",
                    "How are you?",
                    "I'm doing great, how about you?",
                ],
                max_height=400,
                config=chat_config,
            )
            return chatbot
        except Exception as e:
            mo.md(f"**Error initializing chat**: {str(e)}")
            return None


    # Display the chat interface
    chatbot = create_chat(config_form)
    chatbot
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    ## Notes on AWS Bedrock Usage

    1. **Model Access**: You need to request access to the specific models you want to use in the AWS Bedrock console.

    2. **Pricing**: Using AWS Bedrock incurs usage costs based on the number of input and output tokens. Check the [AWS Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) for details.

    3. **Regions**: AWS Bedrock is not available in all AWS regions. Make sure to choose a region where Bedrock is available.

    4. **Authentication**: This example uses the standard AWS credential chain (environment variables, AWS config files, or instance profiles). You can also provide explicit credentials when creating the model.

    5. **Troubleshooting**: If you encounter issues, check:
    - That your AWS credentials are configured correctly
    - That you have requested model access in the AWS Bedrock console
    - That you're using a region where the selected model is available
    """
    )
    return


if __name__ == "__main__":
    app.run()
