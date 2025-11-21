# Delta-Based Streaming Implementation Plan

## Quick Reference

**Current State**: `mo.ui.chat` expects generators to yield accumulated text
**Target State**: `mo.ui.chat` accepts both delta and accumulated modes with auto-detection
**Primary Goal**: Align with OpenAI/Anthropic/AI SDK standards while maintaining backward compatibility

---

## Phase 1: Core Implementation

### 1.1 Add Streaming Mode Detection

**File**: `marimo/_plugins/ui/_impl/chat/chat.py`

```python
from typing import Literal

StreamingMode = Literal["delta", "accumulated", "auto"]

def _detect_streaming_mode(self, model: Any) -> StreamingMode:
    """Detect whether the model yields deltas or accumulated text.
    
    Returns:
        "delta" if model is a marimo ChatModel or has _marimo_uses_deltas=True
        "accumulated" otherwise (legacy behavior)
    """
    from marimo._ai.llm import ChatModel
    
    # Check if it's a marimo ChatModel
    if isinstance(model, ChatModel):
        return "delta"
    
    # Check for explicit marker
    if getattr(model, '_marimo_uses_deltas', False):
        return "delta"
    
    # Default to legacy accumulated mode for custom functions
    return "accumulated"
```

### 1.2 Update Streaming Response Handler

**File**: `marimo/_plugins/ui/_impl/chat/chat.py`

```python
async def _handle_streaming_response(
    self, response: Any, streaming_mode: Optional[str] = None
) -> str:
    """Handle streaming from both sync and async generators.
    
    Args:
        response: Generator yielding strings
        streaming_mode: "delta", "accumulated", or None for auto-detect
    """
    if streaming_mode is None:
        streaming_mode = self._detect_streaming_mode(self._model)
    
    message_id = str(uuid.uuid4())
    latest_response = None
    accumulated_text = ""
    is_delta_mode = streaming_mode == "delta"

    # Use async for if it's an async generator
    if inspect.isasyncgen(response):
        async for latest_response in response:
            if is_delta_mode:
                # Delta mode: accumulate the deltas
                delta = str(latest_response)
                accumulated_text += delta
            else:
                # Accumulated mode: use the full text as-is
                accumulated_text = str(latest_response)
            
            self._send_message(
                {
                    "type": "stream_chunk",
                    "message_id": message_id,
                    "content": accumulated_text,
                    "is_final": False,
                },
                buffers=None,
            )
    else:
        # Handle sync generators
        for latest_response in response:
            if is_delta_mode:
                delta = str(latest_response)
                accumulated_text += delta
            else:
                accumulated_text = str(latest_response)
            
            self._send_message(
                {
                    "type": "stream_chunk",
                    "message_id": message_id,
                    "content": accumulated_text,
                    "is_final": False,
                },
                buffers=None,
            )

    # Send final message
    if latest_response is not None:
        self._send_message(
            {
                "type": "stream_chunk",
                "message_id": message_id,
                "content": accumulated_text,
                "is_final": True,
            },
            buffers=None,
        )

    return (
        str(latest_response)
        if latest_response is not None and not is_delta_mode
        else accumulated_text
    )
```

### 1.3 Update ChatModel Base Class

**File**: `marimo/_ai/llm/_impl.py`

Add marker to base class:

```python
class ChatModel:
    """Base class for chat models."""
    
    # Marker for delta-based streaming
    _marimo_uses_deltas = True
    
    # ... rest of implementation
```

### 1.4 Optional: Add Explicit Parameter

**File**: `marimo/_plugins/ui/_impl/chat/chat.py`

```python
def __init__(
    self,
    model: Callable[[list[ChatMessage], ChatModelConfig], object],
    *,
    prompts: Optional[list[str]] = None,
    on_message: Optional[Callable[[list[ChatMessage]], None]] = None,
    show_configuration_controls: bool = False,
    config: Optional[ChatModelConfigDict] = DEFAULT_CONFIG,
    allow_attachments: Union[bool, list[str]] = False,
    max_height: Optional[int] = None,
    streaming_mode: Optional[StreamingMode] = None,  # ← NEW
) -> None:
    """Initialize chat UI.
    
    Args:
        ...
        streaming_mode: How generator yields are interpreted:
            - "delta": Each yield is a new chunk to append (standard streaming)
            - "accumulated": Each yield is the full text so far (legacy)
            - None: Auto-detect based on model type (recommended)
    """
    self._streaming_mode = streaming_mode
    # ... rest of init
```

---

## Phase 2: Testing

### 2.1 Unit Tests

**File**: `tests/_plugins/test_chat_streaming.py` (new file)

```python
import pytest
import marimo as mo

class TestDeltaStreaming:
    """Test delta-based streaming mode."""
    
    async def test_delta_mode_accumulates_correctly(self):
        """Delta mode should accumulate yielded chunks."""
        
        async def delta_gen():
            yield "Hello"
            yield " "
            yield "world"
        
        # Mock the chat to capture messages
        chat = mo.ui.chat(delta_gen)
        chunks_sent = []
        
        original_send = chat._send_message
        def capture_send(msg, **kwargs):
            chunks_sent.append(msg)
            return original_send(msg, **kwargs)
        
        chat._send_message = capture_send
        
        # Mark as delta mode
        delta_gen._marimo_uses_deltas = True
        
        result = await chat._handle_streaming_response(delta_gen())
        
        assert result == "Hello world"
        assert chunks_sent[0]["content"] == "Hello"
        assert chunks_sent[1]["content"] == "Hello "
        assert chunks_sent[2]["content"] == "Hello world"
    
    async def test_accumulated_mode_uses_full_text(self):
        """Accumulated mode should use yielded text as-is."""
        
        async def accumulated_gen():
            yield "Hello"
            yield "Hello "
            yield "Hello world"
        
        chat = mo.ui.chat(accumulated_gen)
        chunks_sent = []
        
        original_send = chat._send_message
        def capture_send(msg, **kwargs):
            chunks_sent.append(msg)
            return original_send(msg, **kwargs)
        
        chat._send_message = capture_send
        
        result = await chat._handle_streaming_response(
            accumulated_gen(), 
            streaming_mode="accumulated"
        )
        
        assert result == "Hello world"
        assert chunks_sent[0]["content"] == "Hello"
        assert chunks_sent[1]["content"] == "Hello "
        assert chunks_sent[2]["content"] == "Hello world"
    
    def test_chatmodel_detected_as_delta_mode(self):
        """ChatModel instances should be detected as delta mode."""
        from marimo._ai.llm import ChatModel
        
        # Mock model
        class MockModel(ChatModel):
            pass
        
        chat = mo.ui.chat(MockModel())
        mode = chat._detect_streaming_mode(chat._model)
        
        assert mode == "delta"
    
    def test_custom_function_detected_as_accumulated_mode(self):
        """Custom functions should default to accumulated mode."""
        
        async def custom_fn(messages, config):
            yield "text"
        
        chat = mo.ui.chat(custom_fn)
        mode = chat._detect_streaming_mode(chat._model)
        
        assert mode == "accumulated"
```

### 2.2 Integration Test with Real Models

**File**: `tests/_ai/test_llm_streaming.py`

```python
import pytest
import os

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY"
)
async def test_openai_streams_deltas(self):
    """Test that OpenAI model streams efficiently with deltas."""
    import marimo as mo
    
    model = mo.ai.llm.openai(
        "gpt-4o-mini",
        api_key=os.environ["OPENAI_API_KEY"],
    )
    
    chatbot = mo.ui.chat(model)
    
    # Track bandwidth
    total_bytes = 0
    chunk_count = 0
    
    original_send = chatbot._send_message
    def measure_send(msg, **kwargs):
        nonlocal total_bytes, chunk_count
        if msg.get("type") == "stream_chunk":
            total_bytes += len(msg["content"])
            chunk_count += 1
        return original_send(msg, **kwargs)
    
    chatbot._send_message = measure_send
    
    # Send a message
    response = await chatbot._send_prompt(
        SendMessageRequest(
            messages=[
                ChatMessage(role="user", content="Say 'Hello world' and nothing else")
            ],
            config={}
        )
    )
    
    # With delta mode, total bytes should be close to response length * chunk_count
    # With accumulated mode, it would be much higher
    assert response == "Hello world"
    
    # In delta mode: ~11 bytes * N chunks = efficient
    # In accumulated mode: 5 + 10 + 11 = 26 bytes for 3 words = inefficient
    # Since OpenAI streams many small tokens, delta is much better
    print(f"Total bytes: {total_bytes}, Chunks: {chunk_count}")
```

### 2.3 E2E Test

**File**: `frontend/e2e-tests/chat-delta-streaming.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test('OpenAI chatbot streams deltas efficiently', async ({ page }) => {
  await page.goto('/examples/ai/chat/openai_example.py');
  
  // Fill in API key if needed
  const apiKeyInput = await page.locator('input[type="password"]');
  if (await apiKeyInput.isVisible()) {
    await apiKeyInput.fill(process.env.OPENAI_API_KEY || '');
  }
  
  // Send a message
  await page.fill('[data-testid="chat-input"]', 'Count to 5');
  await page.click('[data-testid="chat-send"]');
  
  // Track network traffic to verify efficient streaming
  let streamChunks = 0;
  page.on('websocket', ws => {
    ws.on('framereceived', frame => {
      const data = frame.payload.toString();
      if (data.includes('stream_chunk')) {
        streamChunks++;
      }
    });
  });
  
  // Wait for response
  await page.waitForSelector('[data-role="assistant"]');
  
  const response = await page.locator('[data-role="assistant"]').last().textContent();
  
  expect(response).toContain('1');
  expect(response).toContain('5');
  expect(streamChunks).toBeGreaterThan(5); // Many small chunks = good
});
```

---

## Phase 3: Documentation

### 3.1 Update API Documentation

**File**: `docs/api/inputs/chat.md`

Add section:

```markdown
## Streaming Modes

`mo.ui.chat` supports two streaming modes:

### Delta Mode (Default for `mo.ai.llm` models)

In delta mode, your generator yields **individual chunks** that are appended:

\`\`\`python
async def my_model(messages, config):
    # Stream individual words
    for word in ["Hello", " ", "world"]:
        yield word  # Each yield is a delta
\`\`\`

This is the standard pattern used by OpenAI, Anthropic, and the AI SDK. It's more efficient because only new content is transmitted.

**When to use**: Always prefer delta mode for new code. All `mo.ai.llm` models use delta mode automatically.

### Accumulated Mode (Legacy)

In accumulated mode, your generator yields the **full text so far**:

\`\`\`python
async def my_model(messages, config):
    accumulated = ""
    for word in ["Hello", " ", "world"]:
        accumulated += word
        yield accumulated  # Each yield is the full text
\`\`\`

**When to use**: Only for backward compatibility with existing custom functions.

### Explicit Mode Selection

You can explicitly set the streaming mode:

\`\`\`python
chatbot = mo.ui.chat(
    my_model,
    streaming_mode="delta"  # or "accumulated"
)
\`\`\`

By default, marimo auto-detects the mode:
- `mo.ai.llm` models → delta mode
- Custom functions → accumulated mode
```

### 3.2 Update Example

**File**: `examples/ai/chat/streaming_custom.py`

Update to show both modes:

```python
@app.cell
def _(mo):
    mo.md("""
    ## Streaming Modes
    
    There are two ways to stream responses:
    
    **1. Delta Mode (Recommended)** - Yield individual chunks:
    
    ```python
    async def delta_model(messages, config):
        for word in ["Hello", "world"]:
            yield word + " "  # Yield deltas
    ```
    
    **2. Accumulated Mode (Legacy)** - Yield full text:
    
    ```python
    async def accumulated_model(messages, config):
        text = ""
        for word in ["Hello", "world"]:
            text += word + " "
            yield text  # Yield accumulated
    ```
    
    Delta mode is more efficient and aligns with industry standards.
    """)
    return
```

### 3.3 Add Migration Guide

**File**: `docs/guides/migration/streaming-delta.md` (new)

```markdown
# Migrating to Delta-Based Streaming

## Overview

As of marimo v0.x.x, `mo.ui.chat` supports delta-based streaming, which is more efficient and aligns with industry standards (OpenAI, Anthropic, AI SDK).

## What Changed

### Before (Accumulated Mode)

```python
async def my_model(messages, config):
    accumulated = ""
    for word in response.split():
        accumulated += word + " "
        yield accumulated  # ❌ Yields full text each time
```

### After (Delta Mode)

```python
async def my_model(messages, config):
    for word in response.split():
        yield word + " "  # ✅ Yields only the delta
```

## Do I Need to Change My Code?

**If you're using `mo.ai.llm` models**: No changes needed! They already use delta mode.

**If you have custom streaming functions**: Your code will continue to work, but you should migrate to delta mode for better performance.

## How to Migrate

### Step 1: Update Your Generator

Change from accumulating to yielding deltas:

```python
# Old
async def my_model(messages, config):
    response = ""
    for chunk in stream:
        response += chunk
        yield response

# New
async def my_model(messages, config):
    for chunk in stream:
        yield chunk  # Just yield the chunk directly
```

### Step 2: (Optional) Mark Your Function

If you want to explicitly indicate delta mode:

```python
async def my_model(messages, config):
    for chunk in stream:
        yield chunk

my_model._marimo_uses_deltas = True
```

Or set it explicitly in the chat UI:

```python
chatbot = mo.ui.chat(my_model, streaming_mode="delta")
```

## Why Delta Mode?

- **More efficient**: Only transmits new content (99% bandwidth reduction for long responses)
- **Industry standard**: Matches OpenAI, Anthropic, and AI SDK patterns
- **Simpler code**: No need to maintain accumulator state

## Backward Compatibility

Legacy accumulated mode is still supported and will be auto-detected for custom functions. No breaking changes in this release.
```

---

## Phase 4: Logging and Debugging

### 4.1 Add Debug Logging

**File**: `marimo/_plugins/ui/_impl/chat/chat.py`

```python
from marimo import _loggers

LOGGER = _loggers.marimo_logger()

async def _handle_streaming_response(
    self, response: Any, streaming_mode: Optional[str] = None
) -> str:
    if streaming_mode is None:
        streaming_mode = self._detect_streaming_mode(self._model)
    
    LOGGER.debug(
        "Starting stream in %s mode for model %s",
        streaming_mode,
        type(self._model).__name__
    )
    
    # ... rest of implementation
    
    LOGGER.debug(
        "Stream completed: %d bytes accumulated from %d chunks",
        len(accumulated_text),
        chunk_count
    )
```

### 4.2 Add Heuristic Warning

Detect if user is mixing modes:

```python
if is_delta_mode:
    # Check if the "deltas" look suspiciously like accumulated text
    if len(accumulated_text) > len(delta) * 50:
        LOGGER.warning(
            "Stream appears to yield accumulated text in delta mode. "
            "If you're maintaining an accumulator in your function, "
            "set streaming_mode='accumulated' or yield deltas directly."
        )
```

---

## Phase 5: Rollout

### 5.1 Version 0.x.x (Non-Breaking)

- ✅ Add delta mode with auto-detection
- ✅ All tests passing
- ✅ Documentation updated
- ✅ Examples updated
- ✅ Backward compatible

### 5.2 Version 0.x+1.x (Deprecation Warning)

- Add deprecation warning for accumulated mode:
  ```python
  if streaming_mode == "accumulated":
      warnings.warn(
          "Accumulated streaming mode is deprecated and will be removed in v1.0. "
          "Please migrate to delta mode. See: https://docs.marimo.io/guides/migration/streaming-delta",
          DeprecationWarning,
          stacklevel=2
      )
  ```

### 5.3 Version 1.0.0 (Breaking Change)

- Remove accumulated mode
- All generators must yield deltas
- Clean up detection logic

---

## Success Criteria

- [ ] Auto-detection works for `ChatModel` instances
- [ ] Custom functions still work (backward compatible)
- [ ] Unit tests cover both modes
- [ ] E2E tests verify OpenAI streaming efficiency
- [ ] Documentation clearly explains both modes
- [ ] Migration guide available
- [ ] Performance improvement measurable (use profiling)
- [ ] No regressions in existing examples

---

## Files to Modify

### Backend (Python)
1. `marimo/_plugins/ui/_impl/chat/chat.py` - Core implementation
2. `marimo/_ai/llm/_impl.py` - Add marker to ChatModel
3. `tests/_plugins/test_chat_streaming.py` - New test file
4. `tests/_ai/test_llm_streaming.py` - Integration tests

### Frontend (TypeScript)
- No changes needed! Frontend already handles replacement.

### Documentation
1. `docs/api/inputs/chat.md` - Update API docs
2. `docs/guides/migration/streaming-delta.md` - New migration guide
3. `examples/ai/chat/streaming_custom.py` - Update example
4. `examples/ai/chat/delta_streaming.py` - New example (optional)

### Tests
1. `frontend/e2e-tests/chat-delta-streaming.spec.ts` - New E2E test

---

## Estimated Effort

- **Core Implementation**: 4-6 hours
- **Testing**: 4-6 hours
- **Documentation**: 2-3 hours
- **Review & Polish**: 2-3 hours

**Total**: 12-18 hours (1.5-2 days)

---

## Questions to Answer

1. Should we add a `streaming_mode` parameter to `mo.ui.chat.__init__`?
   - **Recommendation**: Yes, for explicit control and testing

2. Should we warn users if heuristics suggest mode mismatch?
   - **Recommendation**: Yes, but only in debug logs to avoid noise

3. Do we need both sync and async generator support in delta mode?
   - **Recommendation**: Yes, for consistency

4. Should `mo.ai.llm` models expose the raw stream or pre-accumulate?
   - **Recommendation**: Expose raw stream (deltas) and let chat handler accumulate

5. Do we need a way to test streaming mode in production?
   - **Recommendation**: Add a debug endpoint or log message

---

## Next Steps

1. Review this plan with the team
2. Create a GitHub issue with this plan
3. Implement Phase 1 (core changes)
4. Write tests (Phase 2)
5. Update docs (Phase 3)
6. Create PR for review

