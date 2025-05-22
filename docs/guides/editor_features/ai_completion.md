# AI-assisted coding

marimo is an AI-native editor, with support for full-cell AI code generation:

* generating new cells from a prompt
* refactoring existing cells from a prompt
* generating entire notebooks

as well as inline copilots (like GitHub Copilot).

This guide provides an overview of these features and how to configure them.

!!! tip "Locating your marimo.toml config file"

    Various instructions in this guide refer to the marimo.toml configuration
    file. Locate this file with `marimo config show | head`.

## Generating cells with AI

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
your `marimo.toml` configuration file. Prefer going through the notebook settings.

To locate your configuration file, run:

```bash
marimo config show
```

At the top, the path to your `marimo.toml` file will be shown.

Below we describe how to connect marimo to your AI provider.

#### OpenAI

1. Install openai: `pip install openai`

2. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.open_ai]
# Get your API key from https://platform.openai.com/account/api-keys
api_key = "sk-proj-..."
# Choose a model, we recommend "gpt-4-turbo"
model = "gpt-4-turbo"
# Available models: gpt-4-turbo-preview, gpt-4, gpt-3.5-turbo
# See https://platform.openai.com/docs/models for all available models

# Change the base_url if you are using a different OpenAI-compatible API
base_url = "https://api.openai.com/v1"
```

#### Anthropic

To use Anthropic with marimo:

1. Sign up for an account at [Anthropic](https://console.anthropic.com/) and grab your [Anthropic Key](https://console.anthropic.com/settings/keys).
2. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.open_ai]
model = "claude-3-7-sonnet-20250219"
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
   - AWS CLI: Run `aws configure` to set up credentials
   - Environment variables: Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
   - AWS credentials file at `~/.aws/credentials`
5. Add the following to your `marimo.toml`:

```toml title="marimo.toml"
[ai.open_ai]
model = "bedrock/anthropic.claude-3-sonnet-20240229"
# Models are identified by bedrock/provider.model_name
# Examples:
# - bedrock/anthropic.claude-3-sonnet-20240229
# - bedrock/meta.llama3-8b-instruct-v1:0
# - bedrock/amazon.titan-text-express-v1
# - bedrock/cohere.command-r-plus-v1

[ai.bedrock]
region_name = "us-east-1" # AWS region where Bedrock is available
# Optional AWS profile name (from ~/.aws/credentials)
profile_name = "my-profile" 
```

If you're using an AWS named profile different from your default, specify the profile_name. For explicit credentials (not recommended), you can use environment variables instead.

#### Google AI

To use Google AI with marimo:

1. Sign up for an account at [Google AI Studio](https://aistudio.google.com/app/apikey) and obtain your API key.
2. Install the Google AI Python client: `pip install google-generativeai`
3. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.open_ai]
model = "gemini-1.5-flash"
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
[ai.open_ai]
model = "gpt-4o"
api_key = "gho_..."
base_url = "https://api.githubcopilot.com/"
```

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

5. Open a new terminal and start marimo:

   ```bash
   marimo edit notebook.py
   ```

6. Add the following to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.open_ai]
api_key = "ollama" # This is not used, but required
model = "codellama" # or another model from `ollama ls`
base_url = "http://127.0.0.1:11434/v1"
```

#### Other AI providers

marimo supports OpenAI's API by default. Many providers offer OpenAI API-compatible endpoints, which can be used by simply changing the `base_url` in your configuration. For example, providers like [GROQ](https://console.groq.com/docs/openai) and [DeepSeek](https://platform.deepseek.com) follow this pattern.

??? tip "Using OpenAI-compatible providers (e.g., DeepSeek)"

    === "Via marimo.toml"

        Add the following configuration to your `marimo.toml` file:

        ```toml
        [ai.open_ai]
        api_key = "dsk-..." # Your provider's API key
        model = "deepseek-chat" # or "deepseek-reasoner"
        base_url = "https://api.deepseek.com/"
        ```

    === "Via UI Settings"

        1. Open marimo's Settings panel
        2. Navigate to the AI section
        3. Enter your provider's API key in the "OpenAI API Key" field
        4. Under AI Assist settings:
           - Set Base URL to your provider's endpoint (e.g., `https://api.deepseek.com`)
           - Set Model to your chosen model (e.g., `deepseek-chat` or `deepseek-reasoner`)

For a comprehensive list of compatible providers and their configurations, please refer to the [liteLLM Providers documentation](https://litellm.vercel.app/docs/providers).

For providers not compatible with OpenAI's API, please submit a [feature request](https://github.com/marimo-team/marimo/issues/new?template=feature_request.yaml) or "thumbs up" an existing one.

## Copilots

### GitHub Copilot

The marimo editor natively supports [GitHub Copilot](https://copilot.github.com/),
an AI pair programmer, similar to VS Code:

1. Install [Node.js](https://nodejs.org/en/download).
2. Enable Copilot via the settings menu in the marimo editor.

_GitHUb Copilot is not yet available in our conda distribution; please install
marimo using `pip`/`uv` if you need Copilot._

### Windsurf Copilot

Windsurf (formerly codeium) provides a free coding copilot. You can try
setting up Windsurf with the following:

1. Go to the Windsurf website and sign up for an account: <https://windsurf.com/>
2. Try the method from: <https://github.com/leona/helix-gpt/discussions/60>

Add your key to your marimo.toml file (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[completion]
copilot = "codeium"
codeium_api_key = ""
```

For official support, please ping the Windsurf team and ask them to support marimo.

??? note "Alternative: Obtain Windsurf API key using VS Code"

    1. Go to the Codeium website and sign up for an account: <https://codeium.com/>
    2. Install the [Codeium Visual Studio Code extension](vscode:extension/codeium.codeium) (see [here](https://codeium.com/vscode_tutorial) for complete guide)
    3. Sign in to your Codeium account in the VS Code extension
    4. Select the Codeium icon on the Activity bar (left side), which opens the Codeium pane
    5. Select the **Settings** button (gear icon) in the top-right corner of the Codeium pane

    <div align="center">
      <figure>
        <img src="/_static/docs-ai-completion-codeium-vscode.png"/>
        <figcaption>Open Codeium settings</figcaption>
    </figure>
    </div>

    6. Click the **Download** link under the **Extension Diagnostics** section
    7. Open the diagnostic file and search for `apiKey`

    <div align="center">
      <figure>
        <img src="/_static/docs-ai-completion-codeium-vscode-download-diagnostics.png"/>
        <figcaption>Download diagnostics file with API key</figcaption>
      </figure>
    </div>

    8. Copy the value of the `apiKey` to `$XDG_CONFIG_HOME/marimo/marimo.toml`:

    ```toml title="marimo.toml"
    [completion]
    codeium_api_key = "a1e8..."  # <-- paste your API key here
    copilot = "codeium"
    activate_on_typing = true
    ```

### Custom copilots

marimo also supports integrating with custom LLM providers for code completion suggestions. This allows you to use your own LLM service to provide in-line code suggestions based on internal providers or local models (e.g. Ollama). You may also use OpenAI, Anthropic, or Google AI by providing your own API keys.

To configure a custom copilot:

1. Ensure you have an LLM provider that offers API access for code completion (either external or running locally)
2. Add the following configuration to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[completion]
copilot = "custom"
api_key = "your-llm-api-key"
model = "your-llm-model-name"
base_url = "http://127.0.0.1:11434/v1" # or https://your-llm-api-endpoint.com
```

The configuration options include:

* `api_key`: Your LLM provider's API key. This may not be required for local models, so you can set it to any random string.
* `model`: The specific model to use for completion suggestions.
* `base_url`: The endpoint URL for your LLM provider's API
