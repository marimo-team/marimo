# AI-assisted coding

marimo is an AI-native editor, with support for full-cell AI code generation:

* generating new cells from a prompt
* refactoring existing cells from a prompt
* generating entire notebooks

as well as inline autocompletion (like GitHub Copilot).

marimo's AI assistant is specialized for working with data: unlike traditional
assistants that only have access to the text of your program, marimo's assistant
has access to the values of variables in memory, letting it code against
your dataframe and database schemas.

This guide provides an overview of these features and how to configure them.

!!! tip "Locating your marimo.toml config file"

    Various instructions in this guide refer to the marimo.toml configuration
    file. Locate this file with `marimo config show | head`.

## Generating cells with AI

<video autoplay muted loop playsinline width="100%" height="100%" align="center">
  <source src="/_static/readme-generate-with-ai.mp4" type="video/mp4">
</video>

marimo has built-in support for generating and refactoring code with LLMs.
marimo works with hosted AI providers, such as OpenAI, Anthropic, and Google,
as well as local models served via Ollama.

**Enabling AI code generation.** To enable AI code generation, first install
required dependencies through the notebook settings.

<div align="center">
<figure>
<img src="/_static/docs-ai-install.png" width="740px"/>
<figcaption>Install required dependencies for AI generation through the notebook settings.</figcaption>
</figure>
</div>

Then configure your LLM provider through the AI tab in the settings menu; see
the section on [connecting your LLM](#connecting-to-an-llm) for detailed instructions.

### Variable context

marimo's AI assistant has your notebook code as context. You can additionally
pass variables and their values to the assistant by referencing them by name
with `@`. For example, to include the columns of a dataframe `df` in your
prompt, write `@df`.

<div align="center">
<figure>
<img src="/_static/docs-ai-variables.png" width="740px"/>
<figcaption>Pass variables to your prompt by tagging them with `@`.</figcaption>
</figure>
</div>

### Refactor existing cells

Make edits to an existing cell by hitting `Ctrl/Cmd-shift-e`, which opens a prompt box
that has your cell's code as input.

<div align="center">
<figure>
<video src="/_static/ai-completion.mp4" controls="controls" width="100%" height="100%"></video>
<figcaption>Use AI to modify a cell by pressing `Ctrl/Cmd-Shift-e`.</figcaption>
</figure>
</div>

### Generate new cells

#### Generate with AI button

At the bottom of every notebook is a button titled "Generate with AI". Click this
button to add entirely new cells to your notebook.

#### Chat panel

The chat panel on the left sidebar lets you chat with an LLM and ask questions
aboutyour notebook. The LLM can also generate code cells that you can insert
into your notebook.

??? tip "See the chat panel in action"

    <iframe width="740" height="420" src="https://www.youtube.com/embed/4DC1E2UBwAM?si=zzrzl0VlvOU6JiZP" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

### Generating entire notebooks

Generate entire notebooks with `marimo new PROMPT` at the command-line; see the
[text-to-notebook docs](../generate_with_ai/text_to_notebook.md) to learn more.

### Custom rules

You can customize how the AI assistant behaves by adding rules in the marimo settings. These rules help ensure consistent code generation across all AI providers. You can find more information about marimo's supported plotting libraries and data handling in the [plotting guide](../working_with_data/plotting.md#plotting) and [working with data guide](../working_with_data/index.md).

<div align="center">
  <figure>
    <img src="/_static/docs-ai-completion-custom-assist-rules.png"/>
    <figcaption>Configure custom AI rules in settings</figcaption>
  </figure>
</div>

For example, you can add rules about:

* Preferred plotting libraries (matplotlib, plotly, altair)
* Data handling practices
* Code style conventions
* Error handling preferences

Example custom rules:

```
Use plotly for interactive visualizations and matplotlib for static plots
Prefer polars over pandas for data manipulation due to better performance
Include docstrings for all functions using NumPy style
Use Type hints for all function parameters and return values
Handle errors with try/except blocks and provide informative error messages
Follow PEP 8 style guidelines
When working with data:
- Use altair, plotly for declarative visualizations
- Prefer polars over pandas
- Ensure proper error handling for data operations
For plotting:
- Use px.scatter for scatter plots
- Use px.line for time series
- Include proper axis labels and titles
- Set appropriate color schemes
```

### Connecting to an LLM

You can connect to an LLM through the notebook settings menu, or by manually editing
your `marimo.toml` configuration file. **Prefer going through the notebook settings menu.**

You can configure the following providers:

* OpenAI
* Anthropic
* AWS Bedrock
* Google AI
* GitHub
* Ollama
* and any OpenAI-compatible provider

To locate your configuration file, run:

```bash
marimo config show
```

At the top, the path to your `marimo.toml` file will be shown.

#### Model roles and provider routing

marimo supports three different AI model roles, each serving a specific purpose:

* **`chat_model`**: Used for the chat panel
* **`edit_model`**: Used for refactoring existing cells (Ctrl/Cmd-Shift-E) and generating new cells with the "Generate with AI" button.
* **`autocomplete_model`**: Used for inline code autocompletion

Models are specified using the format `provider/model-name`, where the provider prefix routes the request to the appropriate configuration section:

```toml title="marimo.toml"
[ai.models]
chat_model = "openai/gpt-4o-mini"           # Routes to OpenAI config
edit_model = "anthropic/claude-3-sonnet"    # Routes to Anthropic config
autocomplete_model = "ollama/codellama"     # Routes to Ollama config
```

#### Custom models

You can also add custom models to appear in the model selection dropdown.

```toml title="marimo.toml"
[ai.models]
custom_models = ["ollama/somemodel"]
```

Below we describe how to connect marimo to your AI provider.

#### OpenAI

1. Install openai: `pip install openai`

2. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.models]
# Choose for chat
chat_model = "openai/gpt-4o-mini"
# Or choose for edit
edit_model = "openai/gpt-4o-mini"

[ai.open_ai]
# Get your API key from https://platform.openai.com/account/api-keys
api_key = "sk-proj-..."
# Available models: gpt-4o-mini, gpt-4o, gpt-4, gpt-3.5-turbo
# See https://platform.openai.com/docs/models for all available models

# Change the base_url if you are using a different OpenAI-compatible API
# different from one of the providers listed below
base_url = "https://api.openai.com/v1"
```

#### Anthropic

To use Anthropic with marimo:

1. Sign up for an account at [Anthropic](https://console.anthropic.com/) and grab your [Anthropic Key](https://console.anthropic.com/settings/keys).
2. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.models]
chat_model = "anthropic/claude-3-7-sonnet-latest"
# or any model from https://docs.anthropic.com/en/docs/about-claude/models

[ai.anthropic]
api_key = "sk-ant-..."
```

#### AWS Bedrock

AWS Bedrock provides access to foundation models from leading AI companies through a unified AWS API.

To use AWS Bedrock with marimo:

1. Set up an [AWS account](https://aws.amazon.com/) with access to the AWS Bedrock service.
2. [Enable model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) for the specific models you want to use in the AWS Bedrock console.
3. Install the boto3 Python client: `pip install boto3`
4. Configure AWS credentials using one of these methods:
   * AWS CLI: Run `aws configure` to set up credentials
   * Environment variables: Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
   * AWS credentials file at `~/.aws/credentials`
5. Add the following to your `marimo.toml`:

```toml title="marimo.toml"
[ai.models]
chat_model = "bedrock/anthropic.claude-3-sonnet-latest"

[ai.bedrock]
region_name = "us-east-1" # AWS region where Bedrock is available
# Optional AWS profile name (from ~/.aws/credentials)
profile_name = "my-profile"
```

If you're using an AWS named profile different from your default, specify the profile_name. For explicit credentials (not recommended), you can use environment variables instead.

#### Google AI

To use Google AI with marimo:

1. Sign up for an account at [Google AI Studio](https://aistudio.google.com/app/apikey) and obtain your API key.
2. Install the Google AI Python client: `pip install google-genai`
3. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.models]
chat_model = "google/gemini-2.5-pro"
# or any model from https://ai.google.dev/gemini-api/docs/models/gemini

[ai.google]
api_key = "AI..."
```

#### GitHub Copilot

You can use your GitHub Copilot for code refactoring or the chat panel. This requires a GitHub Copilot subscription.

1. Download the `gh` CLI from [here](https://cli.github.com/).
2. Create a token with `gh auth token` and copy the token.
3. Add the token to your `marimo.toml` (or configure in the UI settings in the editor).

```toml title="marimo.toml"
[ai.models]
chat_model = "github/gpt-4o-mini"

[ai.github]
api_key = "gho_..."
```

??? question "My token starts with `ghp_` instead of `gho_`?"

    This usually happens when you previously authenticated `gh` by pasting a _personal_ access token (`ghp_...`). However, GitHub Copilot is not available through `ghp_...`, and you will encounter errors such as:

    > bad request: Personal Access Tokens are not supported for this endpoint

    To resolve this issue, you could switch to an _OAuth_ access token (`gho_...`):

    1. Re-authenticate by running `gh auth login`.
    2. Choose _Login with a web browser_ (instead of _Paste an authentication token_) this time.

#### Local models with Ollama { #using-ollama }

Ollama allows you to run open-source LLMs on your local machine. To integrate Ollama with marimo:

1. Download and install [Ollama](https://ollama.com/).
2. Download the model you want to use:

   ```bash
   # View available models at https://ollama.com/library
   ollama pull llama3.1
   ollama pull codellama  # recommended for code generation

   # View your installed models
   ollama ls
   ```

3. Start the Ollama server in a terminal:

   ```bash
   ollama serve
   # In a new terminal
   ollama run codellama  # or any model from ollama ls
   ```

4. Visit <http://127.0.0.1:11434> to confirm that the server is running.

!!! note "Port already in use"
    If you get a "port already in use" error, you may need to close an existing Ollama instance. On Windows, click the up arrow in the taskbar, find the Ollama icon, and select "Quit". This is a known issue (see [Ollama Issue #3575](https://github.com/ollama/ollama/issues/3575)). Once you've closed the existing Ollama instance, you should be able to run `ollama serve` successfully.

5. Open a new terminal and install the openai client (e.g. `pip install openai`, `uv add openai`)

6. Start marimo:

   ```bash
   marimo edit notebook.py
   ```

??? warning "Important: Use the `/v1` endpoint"

    marimo requires Ollama's OpenAI-compatible API endpoint. Always ensure your `base_url` includes the `/v1` path:

    ```toml
    [ai.ollama]
    base_url = "http://127.0.0.1:11434/v1"  # ✅ Correct - includes /v1
    ```

    **Common mistake:**
    ```toml
    base_url = "http://127.0.0.1:11434"     # ❌ Will cause 404 errors
    ```

    If you encounter 404 errors, verify your model is installed with `ollama ls` and test the endpoint:
    ```bash
    curl http://127.0.0.1:11434/v1/models
    ```

7. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.models]
chat_model = "ollama/llama3.1:latest"
edit_model = "ollama/codellama"
autocomplete_model = "ollama/codellama" # or another model from `ollama ls`
```

#### Other AI providers

marimo supports OpenAI's API by default. Many providers offer OpenAI API-compatible endpoints, which can be used by simply changing the `base_url` in your configuration. For example, providers like [GROQ](https://console.groq.com/docs/openai) and [DeepSeek](https://platform.deepseek.com) follow this pattern.

??? tip "Using OpenAI-compatible providers (e.g., DeepSeek)"

    === "Via UI Settings"

        1. Open marimo's Settings panel
        2. Navigate to the AI section
        3. Enter your provider's API key in the "OpenAI API Key" field
        4. Under AI Assist settings:

           - Set Base URL to your provider's endpoint (e.g., `https://api.deepseek.com`)
           - Set Model to your chosen model (e.g., `deepseek-chat` or `deepseek-reasoner`)

    === "Via marimo.toml"

        Add the following configuration to your `marimo.toml` file:

        ```toml
        [ai.models]
        chat_model = "deepseek/deepseek-chat" # or "deepseek-reasoner"

        [ai.open_ai_compatible]
        api_key = "dsk-..." # Your provider's API key
        base_url = "https://api.deepseek.com/"
        ```

For a comprehensive list of compatible providers and their configurations, please refer to the [liteLLM Providers documentation](https://litellm.vercel.app/docs/providers).

For providers not compatible with OpenAI's API, please submit a [feature request](https://github.com/marimo-team/marimo/issues/new?template=feature_request.yaml) or "thumbs up" an existing one.

## Agents

!!! example "Experimental: Agents"

    marimo also supports external AI agents like Claude Code and Gemini CLI that can interact with your notebooks.
    Learn more in the [agents](agents.md) guide.

## Copilots

### GitHub Copilot

The marimo editor natively supports [GitHub Copilot](https://copilot.github.com/),
an AI pair programmer, similar to VS Code:

1. Install [Node.js](https://nodejs.org/en/download).
2. Enable Copilot via the settings menu in the marimo editor.

_GitHUb Copilot is not yet available in our conda distribution; please install
marimo using `pip`/`uv` if you need Copilot._

### Windsurf Copilot

[Windsurf](https://windsurf.com/) (formerly codeium) provides tab-completion tooling that can also be used from within marimo.

To set up Windsurf:

1. Go to [windsurf.com](https://windsurf.com/) website and sign up for an account.
2. Download the [Windsurf app](https://windsurf.com/download).
3. After installing Windsurf and authenticating, open up the command palette, via <kbd>cmd</kbd>+<kbd>shift</kbd>+<kbd>p</kbd>, and ask it to copy the api key to your clipboard.

![Copy Windsurf API key](/_static/windsurf-api.png)

4a. Configure the UI settings in the editor to use Windsurf.

![Paste Windsurf API key](/_static/windsurf-settings.png)

4b. Alternatively you can also configure the api key from the marimo config file.

```toml title="marimo.toml"
[completion]
copilot = "codeium"
codeium_api_key = ""
```

### Custom copilots

marimo also supports integrating with custom LLM providers for code completion suggestions. This allows you to use your own LLM service to provide in-line code suggestions based on internal providers or local models (e.g. Ollama). You may also use OpenAI, Anthropic, Google, or any other providers by providing your own API keys and configuration.

To configure a custom copilot:

1. Ensure you have an LLM provider that offers API access for code completion (either external or running locally)
2. Add the following configuration to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.models]
autocomplete_model = "provider/model-name"

[completion]
copilot = "custom"
```

The configuration options include:

* `autocomplete_model`: The specific model to use for inline autocompletion.
* `copilot`: The name of the copilot to use for code generation.
