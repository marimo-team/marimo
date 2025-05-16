# Copyright 2024 Marimo. All rights reserved.

import marimo as mo

__generated_with = "0.13.10"
app = mo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# AWS Bedrock Chat Example

This example demonstrates using AWS Bedrock with marimo's chat interface.

AWS Bedrock provides access to foundation models from leading AI companies like Anthropic, Meta, and others.

⚠️ **Note:** You'll need an AWS account with access to the AWS Bedrock service and the specific model you want to use.
""")
    return


@app.cell
def _():
    import os
    import boto3
    import marimo as mo
    
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
                
        return {
            "has_credentials": has_creds
        }
    
    # Run the check
    aws_config = check_aws_config()
    return aws_config, boto3, check_aws_config, mo, os


@app.cell
def _(aws_config, mo):
    # Display AWS configuration status
    if not aws_config["has_credentials"]:
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
        """)
    else:
        mo.md("### ✅ AWS Configuration Detected")
    return


@app.cell
def _(mo):
    # UI for model configuration
    
    # Predefined model options
    model_options = [
        "anthropic.claude-3-sonnet-20240229",
        "anthropic.claude-3-haiku-20240307",
        "meta.llama3-8b-instruct-v1:0",
        "amazon.titan-text-express-v1",
        "cohere.command-r-plus-v1"
    ]
    
    # Region options
    region_options = [
        "us-east-1",
        "us-west-2", 
        "eu-central-1",
        "ap-northeast-1",
        "ap-southeast-1"
    ]
    
    # Model selection
    model = mo.ui.dropdown(
        options=model_options,
        value=model_options[0],
        label="AWS Bedrock Model"
    )
    
    # Region selection
    region = mo.ui.dropdown(
        options=region_options,
        value="us-east-1",
        label="AWS Region"
    )
    
    # Optional profile name
    profile = mo.ui.text(
        value="",
        label="AWS Profile (optional)",
        placeholder="Leave empty to use default credentials"
    )
    
    # System message
    system_message = mo.ui.text_area(
        value="You are a helpful, harmless assistant. Provide clear, concise answers.",
        label="System Message",
        rows=2
    )
    
    # Temperature slider
    temperature = mo.ui.slider(
        value=0.7,
        min=0.0,
        max=1.0,
        step=0.1,
        label="Temperature"
    )
    
    # Max tokens input
    max_tokens = mo.ui.number(
        value=1000,
        min=1,
        max=4096,
        step=1,
        label="Max Tokens"
    )
    
    # Create a form to wrap all inputs
    config_form = mo.ui.form(
        [model, region, profile, system_message, temperature, max_tokens],
        submit_button_text="Update Chat Configuration" 
    )
    
    return config_form, max_tokens, model, profile, region, system_message, temperature


@app.cell
def _(config_form, max_tokens, mo, model, profile, region, system_message, temperature):
    mo.md("## AWS Bedrock Chat")
    
    # Create a refreshable chat component that updates when the form is submitted
    @mo.refresh(config_form)
    def create_chat():
        try:
            # Create chat config
            chat_config = mo.ai.ChatModelConfig(
                temperature=temperature.value,
                max_tokens=max_tokens.value
            )
            
            # Create model with optional profile
            model_kwargs = {
                "model": model.value,
                "region_name": region.value,
                "system_message": system_message.value
            }
            
            # Add profile if specified
            if profile.value.strip():
                model_kwargs["profile_name"] = profile.value.strip()
            
            # Create chat interface
            chatbot = mo.ui.chat(
                mo.ai.llm.bedrock(**model_kwargs),
                config=chat_config
            )
            return chatbot
        except Exception as e:
            mo.md(f"**Error initializing chat**: {str(e)}")
            return None
    
    # Display the chat interface
    chat = create_chat()
    if chat:
        chat
        
    return chat, create_chat


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## Notes on AWS Bedrock Usage

1. **Model Access**: You need to request access to the specific models you want to use in the AWS Bedrock console.

2. **Pricing**: Using AWS Bedrock incurs usage costs based on the number of input and output tokens. Check the [AWS Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) for details.

3. **Regions**: AWS Bedrock is not available in all AWS regions. Make sure to choose a region where Bedrock is available.

4. **Authentication**: This example uses the standard AWS credential chain (environment variables, AWS config files, or instance profiles). You can also provide explicit credentials when creating the model.

5. **Troubleshooting**: If you encounter issues, check:
   - That your AWS credentials are configured correctly
   - That you have requested model access in the AWS Bedrock console
   - That you're using a region where the selected model is available
""")
    return


if __name__ == "__main__":
    app.run()