# Chat

```{eval-rst}
.. marimo-embed::
    :size: large

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

The chat UI element provides an interactive chatbot interface for conversations. It can be customized with different models, including built-in AI models or custom functions.

```{eval-rst}
.. autoclass:: marimo.ui.chat
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.chat.chat
```

## Basic Usage

Here's a simple example using a custom echo model:

```python
import marimo as mo

def echo_model(messages, config):
    return f"Echo: {messages[-1].content}"

chat = mo.ui.chat(echo_model, prompts=["Hello", "How are you?"])
chat
```

## Using a Built-in AI Model

You can use marimo's built-in AI models, such as OpenAI's GPT:

```python
import marimo as mo

chat = mo.ui.chat(
    mo.ai.openai(
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

This returns a list of `ChatMessage` objects, each containing `role` and `content` attributes.

```{eval-rst}
.. autoclass:: ChatMessage
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.chat.types.ChatMessage
```

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

This example demonstrates how you can implement a Retrieval-Augmented Generation (RAG) model within the chat interface.

## Built-in Models

marimo provides several built-in AI models that you can use with the chat UI element.

```{eval-rst}
.. autoclass:: marimo.ai.openai
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.chat.models.openai
```

```{eval-rst}

.. autoclass:: marimo.ai.anthropic
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.chat.models.anthropic
```
