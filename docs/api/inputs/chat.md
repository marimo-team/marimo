# Chat

!!! tip "Looking for example notebooks?"
    For example notebooks, check out [`examples/ai/chat` on our
    GitHub](https://github.com/marimo-team/marimo/tree/main/examples/ai/chat).

/// marimo-embed
    size: large

```python
@app.cell
def __():
    def simple_echo_model(messages, config):
        return f"You said: {messages[-1].content}"

    mo.ui.chat(
        simple_echo_model,
        prompts=["Hello", "How are you?"],
        show_configuration_controls=True
    )
    return
```

///

The chat UI element provides an interactive chatbot interface for
conversations. It can be customized with different models, including built-in
AI models from popular providers or custom functions.

::: marimo.ui.chat

## Basic Usage

Here's a simple example using a custom echo model:

```python
import marimo as mo

def echo_model(messages, config):
    return f"Echo: {messages[-1].content}"

chat = mo.ui.chat(echo_model, prompts=["Hello", "How are you?"])
chat
```

Here, `messages` is a list of [`ChatMessage`][marimo.ai.ChatMessage] objects,
which has `role` (`"user"`, `"assistant"`, or `"system"`) and `content` (the
message string) attributes; `config` is a
[`ChatModelConfig`][marimo.ai.ChatModelConfig] object with various
configuration parameters, which you are free to ignore.

## Using a Built-in AI Model

You can use marimo's built-in AI models, such as OpenAI's GPT:

```python
import marimo as mo

chat = mo.ui.chat(
    mo.ai.llm.openai(
        "gpt-4",
        system_message="You are a helpful assistant.",
    ),
    show_configuration_controls=True
)
chat
```

## Accessing Chat History

You can access the chat history using the `value` attribute:

```python
chat.value
```

This returns a list of [`ChatMessage`][marimo.ai.ChatMessage] objects, each
containing `role`, `content`, and optional `attachments` attributes.

::: marimo.ai.ChatMessage

## Custom Model with Additional Context

Here's an example of a custom model that uses additional context:

```python
import marimo as mo

def rag_model(messages, config):
    question = messages[-1].content
    docs = find_relevant_docs(question)
    context = "\n".join(docs)
    prompt = f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"
    response = query_llm(prompt, config)
    return response

mo.ui.chat(rag_model)
```

This example demonstrates how you can implement a Retrieval-Augmented
Generation (RAG) model within the chat interface.

## Templated Prompts

You can pass sample prompts to `mo.ui.chat` to allow users to select from a
list of predefined prompts. By including a `{{var}}` in the prompt, you can
dynamically insert values into the prompt; a form will be generated to allow
users to fill in the variables.

```python
mo.ui.chat(
    mo.ai.llm.openai("gpt-4o"),
    prompts=[
        "What is the capital of France?",
        "What is the capital of Germany?",
        "What is the capital of {{country}}?",
    ],
)
```

## Including Attachments

You can allow users to upload attachments to their messages by passing an
`allow_attachments` parameter to `mo.ui.chat`.

```python
mo.ui.chat(
    rag_model,
    allow_attachments=["image/png", "image/jpeg"],
    # or True for any attachment type
    # allow_attachments=True,
)
```

## Streaming Responses

Chatbots can stream responses in real-time, creating a more interactive experience
similar to ChatGPT where you see the response appear word-by-word as it's generated.

Responses from built-in models (OpenAI, Anthropic, Google, Groq, Bedrock) are streamed by default.

### How Streaming Works

marimo uses **delta-based streaming**, which follows the industry-standard pattern used by OpenAI, Anthropic, and other AI providers. Your generator function should yield **individual chunks** (deltas) of new content, which marimo automatically accumulates and displays progressively.

### With Custom Models

For custom models, you can use either regular (sync) or async generator functions that yield delta chunks:

**Sync generator (simpler):**

```python
import marimo as mo
import time

def streaming_model(messages, config):
    """Stream responses word by word."""
    response = "This response will appear word by word!"
    words = response.split()

    for word in words:
        yield word + " "  # Yield delta chunks
        time.sleep(0.1)  # Simulate processing delay

chat = mo.ui.chat(streaming_model)
chat
```

**Async generator (for async operations):**

```python
import marimo as mo
import asyncio

async def async_streaming_model(messages, config):
    """Stream responses word by word asynchronously."""
    response = "This response will appear word by word!"
    words = response.split()

    for word in words:
        yield word + " "  # Yield delta chunks
        await asyncio.sleep(0.1)  # Async processing delay

chat = mo.ui.chat(async_streaming_model)
chat
```

Each `yield` sends a new chunk (delta) to marimo, which accumulates and displays
the progressively building response in real-time.

!!! tip "Delta vs Accumulated"
    **Yield deltas, not accumulated text.** Each yield should be **new content only**:

    ✅ **Correct (delta mode):**
    ```python
    yield "Hello"
    yield " "
    yield "world"
    # Result: "Hello world"
    ```

    ❌ **Incorrect (accumulated mode, deprecated):**
    ```python
    yield "Hello"
    yield "Hello "
    yield "Hello world"
    # Inefficient: sends duplicate content
    ```

    Delta mode is more efficient (reduces bandwidth by ~99% for long responses) and aligns with standard streaming APIs.

!!! tip "See streaming examples"
    For complete working examples, check out:

    - [`openai_example.py`](https://github.com/marimo-team/marimo/blob/main/examples/ai/chat/openai_example.py) - OpenAI chatbot with streaming (default)
    - [`streaming_custom.py`](https://github.com/marimo-team/marimo/blob/main/examples/ai/chat/streaming_custom.py) - Custom streaming chatbot
    - [`pydantic_ai_with_thinking_and_tools.py`](https://github.com/marimo-team/marimo/blob/main/examples/ai/chat/pydantic_ai_with_thinking_and_tools.py) - Chatbot with thinking and tools
    - [`wandb_inference_example.py`](https://github.com/marimo-team/marimo/blob/main/examples/ai/chat/wandb_inference_example.py) - W&B Inference with reasoning models

## Built-in Models

marimo provides several built-in AI models that you can use with the chat UI
element.

### OpenAI

```python
import marimo as mo

mo.ui.chat(
    mo.ai.llm.openai(
        "gpt-4o",
        system_message="You are a helpful assistant.",
        api_key="sk-proj-...",
    ),
    show_configuration_controls=True
)
```

::: marimo.ai.llm.openai

### Anthropic

```python
import marimo as mo

mo.ui.chat(
    mo.ai.llm.anthropic(
        "claude-3-5-sonnet-20240620",
        system_message="You are a helpful assistant.",
        api_key="sk-ant-...",
    ),
    show_configuration_controls=True
)
```

::: marimo.ai.llm.anthropic

### Google AI

```python
import marimo as mo

mo.ui.chat(
    mo.ai.llm.google(
        "gemini-1.5-pro-latest",
        system_message="You are a helpful assistant.",
        api_key="AI..",
    ),
    show_configuration_controls=True
)

```

::: marimo.ai.llm.google

### Groq

```python
import marimo as mo

mo.ui.chat(
    mo.ai.llm.groq(
        "llama-3.1-70b-versatile",
        system_message="You are a helpful assistant.",
        api_key="gsk-...",
    ),
    show_configuration_controls=True
)
```

::: marimo.ai.llm.groq

### Pydantic AI (with Tools and Thinking)

The `pydantic_ai` model provides advanced features like **tool calling** and
**thinking/reasoning** support using [pydantic-ai](https://ai.pydantic.dev/).

It works just like other `mo.ai.llm` classes - pass a model string and options.
For full control, you can also pass a pre-configured `Agent` directly.

#### Basic Usage with Tools

```python
import marimo as mo

def get_weather(location: str) -> dict:
    """Get weather for a location."""
    return {"temperature": 72, "conditions": "sunny"}

def calculate(expression: str) -> float:
    """Evaluate a math expression."""
    return eval(expression)

chat = mo.ui.chat(
    mo.ai.llm.pydantic_ai(
        "anthropic:claude-sonnet-4-5",  # or "openai:gpt-4.1", etc.
        tools=[get_weather, calculate],
        instructions="You are a helpful assistant.",
    )
)
chat
```

Tool calls are displayed as collapsible accordions in the chat UI, showing
the tool name, inputs, and outputs.

#### With Thinking/Reasoning

Enable thinking to see the LLM's step-by-step reasoning process:

```python
from pydantic_ai.models.anthropic import AnthropicModelSettings

chat = mo.ui.chat(
    mo.ai.llm.pydantic_ai(
        "anthropic:claude-sonnet-4-5",
        tools=[get_weather],
        instructions="Think step-by-step.",
        model_settings=AnthropicModelSettings(
            max_tokens=8000,
            anthropic_thinking={"type": "enabled", "budget_tokens": 4000},
        ),
    )
)
```

When enabled, a "View reasoning" accordion appears before the response,
showing the LLM's thinking process in real-time.

#### Using a Pre-configured Agent

For full control over Agent configuration, pass a `pydantic_ai.Agent` directly:

```python
from pydantic_ai import Agent

agent = Agent(
    "anthropic:claude-sonnet-4-5",
    tools=[get_weather],
    deps_type=MyDeps,      # Full Agent configuration
    output_type=MyOutput,
    # ... any other Agent options
)

chat = mo.ui.chat(mo.ai.llm.pydantic_ai(agent))
```

#### OpenAI-Compatible Providers (W&B Inference, DeepSeek, etc.)

For custom endpoints, configure a Model object with provider and profile:

```python
import marimo as mo
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.profiles.openai import OpenAIModelProfile

# Configure model with W&B Inference endpoint
model = OpenAIChatModel(
    model_name="deepseek-ai/DeepSeek-R1-0528",
    provider=OpenAIProvider(
        api_key="your-wandb-key",
        base_url="https://api.inference.wandb.ai/v1",
    ),
    profile=OpenAIModelProfile(
        openai_chat_thinking_field="reasoning_content",
    ),
)

chat = mo.ui.chat(
    mo.ai.llm.pydantic_ai(model, instructions="Think step-by-step.")
)
```

This works with any OpenAI-compatible endpoint:

- [W&B Inference](https://docs.wandb.ai/inference/) - Access open-source models with reasoning support
- [DeepSeek](https://platform.deepseek.com/) - DeepSeek models
- [Together AI](https://www.together.ai/) - Various open-source models
- Any other OpenAI-compatible API

See the [pydantic-ai documentation](https://ai.pydantic.dev/) for full
Agent and Model configuration options.

::: marimo.ai.llm.pydantic_ai

## Types

Chatbots can be implemented with a function that receives a list of
[`ChatMessage`][marimo.ai.ChatMessage] objects and a
[`ChatModelConfig`][marimo.ai.ChatModelConfig].

::: marimo.ai.ChatMessage

::: marimo.ai.ChatModelConfig

[`mo.ui.chat`][marimo.ui.chat] can be instantiated with an initial
configuration with a dictionary conforming to the config.

`ChatMessage`s can also include attachments.

::: marimo.ai.ChatAttachment

## Supported Model Providers

We support any OpenAI-compatible endpoint. If you want any specific provider added explicitly (ones that don't abide by the standard OpenAI API format), you can file a [feature request](https://github.com/marimo-team/marimo/issues/new?template=feature_request.yaml).

Normally, overriding the `base_url` parameter should work. Here are some examples:

/// tab | Cerebras

```python
chatbot = mo.ui.chat(
    mo.ai.llm.openai(
        model="llama3.1-8b",
        api_key="csk-...", # insert your key here
        base_url="https://api.cerebras.ai/v1/",
    ),
)
chatbot
```

///

/// tab | Groq

```python
chatbot = mo.ui.chat(
    mo.ai.llm.openai(
        model="llama-3.1-70b-versatile",
        api_key="gsk_...", # insert your key here
        base_url="https://api.groq.com/openai/v1/",
    ),
)
chatbot
```

///

/// tab | xAI

```python
chatbot = mo.ui.chat(
    mo.ai.llm.openai(
        model="grok-beta",
        api_key=key, # insert your key here
        base_url="https://api.x.ai/v1",
    ),
)
chatbot
```

///

!!! note

    We have added examples for GROQ and Cerebras. These providers offer free API keys and are great for trying out Llama models (from Meta). You can sign up on their platforms and integrate with various AI integrations in marimo easily. For more information, refer to the [AI completion documentation in marimo](../../guides/editor_features/ai_completion.md).
