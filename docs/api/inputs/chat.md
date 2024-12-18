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
