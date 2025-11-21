# Marimo Streaming Analysis: Delta vs Accumulated

## Executive Summary

**Current Problem**: Marimo requires generator functions to yield **accumulated text** (e.g., "Hello", "Hello world", "Hello world!"), while industry-standard streaming APIs like OpenAI, Anthropic, and the AI SDK use **delta chunks** (e.g., "Hello", " world", "!").

**Impact**: 
- ❌ Inefficient bandwidth usage (sends full text repeatedly)
- ❌ Non-standard API contract
- ❌ Forces developers to accumulate deltas before yielding
- ❌ Misalignment with upstream streaming APIs

**Recommendation**: Support delta-based streaming as the primary pattern, with backward compatibility for accumulated streaming.

---

## Current Implementation

### Backend: `chat.py` - `_handle_streaming_response`

Located at: `marimo/_plugins/ui/_impl/chat/chat.py:217-265`

```python
async def _handle_streaming_response(self, response: Any) -> str:
    """Handle streaming from both sync and async generators."""
    message_id = str(uuid.uuid4())
    latest_response = None
    accumulated_text = ""

    if inspect.isasyncgen(response):
        async for latest_response in response:  # noqa: B007
            accumulated_text = str(latest_response)  # ← EXPECTS ACCUMULATED
            self._send_message(
                {
                    "type": "stream_chunk",
                    "message_id": message_id,
                    "content": accumulated_text,  # ← SENDS FULL TEXT
                    "is_final": False,
                },
                buffers=None,
            )
```

**Key Issue**: The backend expects `latest_response` to be the **full accumulated text**, not a delta.

### Frontend: `chat-ui.tsx` - Stream Chunk Handler

Located at: `frontend/src/plugins/impl/chat/chat-ui.tsx:215-288`

```typescript
// Listen for streaming chunks from backend
useEventListener(
  props.host as HTMLElementNotDerivedFromRef,
  MarimoIncomingMessageEvent.TYPE,
  (e) => {
    const message = e.detail.message;
    if (message.type === "stream_chunk") {
      const chunkMessage = message as {
        content: string;  // ← RECEIVES FULL ACCUMULATED TEXT
        is_final: boolean;
      };
      
      // Simply replaces the entire message content
      updated[index] = {
        ...messageToUpdate,
        parts: [{ type: "text", text: chunkMessage.content }],  // ← REPLACES
      };
    }
  }
);
```

**Key Issue**: Frontend **replaces** the entire message content on each chunk, rather than **appending** deltas.

### Developer Experience

Current pattern forces this accumulation pattern:

```python
async def streaming_echo_model(messages, config):
    response = "You said: 'Hello world!'"
    words = response.split()
    accumulated = ""  # ← Must maintain accumulator
    
    for word in words:
        accumulated += word + " "  # ← Must accumulate manually
        yield accumulated  # ← Yield full text each time
        await asyncio.sleep(0.2)
```

**Inefficiency Example**: For a 1000-word response:
- Current: Sends ~500KB (1 + 2 + 3 + ... + 1000 words)
- Delta-based: Sends ~1KB (1 + 1 + 1 + ... + 1 words)

---

## Industry Standard: Delta-Based Streaming

### OpenAI Chat Completions API

```json
// Chunk 1
data: {"choices": [{"delta": {"content": "Hello"}}]}

// Chunk 2
data: {"choices": [{"delta": {"content": " world"}}]}

// Chunk 3
data: {"choices": [{"delta": {"content": "!"}}]}

// Client accumulates: "Hello" + " world" + "!" = "Hello world!"
```

### Anthropic Messages API

```json
// Chunk 1
event: content_block_delta
data: {"delta": {"type": "text_delta", "text": "Hello"}}

// Chunk 2
event: content_block_delta
data: {"delta": {"type": "text_delta", "text": " world"}}
```

### Vercel AI SDK (What marimo uses)

The AI SDK already supports delta-based streaming via the AI SDK Stream Protocol:

```typescript
// Text delta chunk format: "0:{delta}\n"
"0:Hello\n"    // Delta: "Hello"
"0: world\n"   // Delta: " world"
"0:!\n"        // Delta: "!"
```

### Why Deltas Are Better

1. **Efficient**: Only transmit new content
2. **Standard**: Matches all major AI APIs
3. **Flexible**: Client controls accumulation/rendering
4. **Composable**: Easy to pipe streams without modification
5. **Aligned**: Marimo's AI completions endpoint (`providers.py`) already uses deltas internally

---

## The Disconnect: Why This Exists

### AI Completions Endpoint (Server)

Located at: `marimo/_server/ai/providers.py:242-390`

The **AI completions endpoint** (used for code generation) already uses delta-based streaming:

```python
async def as_stream_response(
    self, response: StreamT, options: Optional[StreamOptions] = None
) -> AsyncGenerator[str, None]:
    """Convert a stream to an async generator of strings."""
    
    async for chunk in response:
        content = self.extract_content(chunk, tool_calls_order)
        
        for content_data, content_type in content:
            if content_type == "text":
                # Emit text-delta event with the actual content
                yield convert_to_ai_sdk_messages(
                    content_data,  # ← DELTA ONLY
                    "text",
                    current_text_id
                )
                continue
            
            buffer += content_str  # ← Accumulates for final result
            yield buffer           # ← But sends accumulated (?)
```

**Note**: This is partially delta-aware but still maintains an accumulation pattern for some paths.

### Chat UI Element

The `mo.ui.chat` element has its own streaming handler that expects accumulated text. This creates two different streaming contracts:

1. **AI Completions** → Uses AI SDK format (delta-aware)
2. **Chat UI Element** → Uses custom format (accumulation-based)

This inconsistency forces developers to write different code depending on which marimo feature they use.

---

## Proposed Solution

### Option 1: Add Delta Mode (Recommended)

**Pros**: 
- Maintains backward compatibility
- Allows gradual migration
- Explicit opt-in for new behavior

**Cons**: 
- Two code paths to maintain
- Complexity in implementation

#### Implementation

**1. Add a flag to detect delta mode**

```python
# marimo/_plugins/ui/_impl/chat/chat.py

async def _handle_streaming_response(
    self, response: Any, is_delta_mode: bool = False
) -> str:
    """Handle streaming from both sync and async generators.
    
    Args:
        response: Generator yielding strings
        is_delta_mode: If True, treats yielded values as deltas to accumulate.
                      If False, treats yielded values as full accumulated text (legacy).
    """
    message_id = str(uuid.uuid4())
    latest_response = None
    accumulated_text = ""

    if inspect.isasyncgen(response):
        async for latest_response in response:
            if is_delta_mode:
                # New behavior: accumulate deltas
                delta = str(latest_response)
                accumulated_text += delta
            else:
                # Legacy behavior: use full text
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
    # ... similar for sync generators
```

**2. Auto-detect delta mode based on model type**

```python
def _is_delta_mode_model(self, model: Any) -> bool:
    """Check if model uses delta-based streaming."""
    # Check if it's a ChatModel from marimo
    from marimo._ai.llm import ChatModel
    if isinstance(model, ChatModel):
        return True
    
    # Could also check for specific attributes or markers
    return getattr(model, '_marimo_uses_deltas', False)
```

**3. Update ChatModel base class**

```python
# marimo/_ai/llm/_impl.py

class ChatModel:
    """Base class for chat models with delta-based streaming."""
    
    _marimo_uses_deltas = True  # Marker for delta mode
    
    async def _stream(
        self,
        messages: list[ChatMessage],
        config: ChatModelConfig,
    ) -> AsyncGenerator[str, None]:
        """Stream deltas from the model."""
        # Implementation yields deltas
        async for delta in stream:
            yield delta  # ← Yields delta, not accumulated
```

**4. Frontend stays the same**

The frontend already replaces the full content, so it doesn't need changes. The backend accumulation ensures the frontend always receives the full text.

#### Usage

```python
# New delta mode (automatic with mo.ai.llm models)
chatbot = mo.ui.chat(
    mo.ai.llm.openai("gpt-4o", api_key=key),
    # Delta mode auto-detected
)

# Legacy accumulated mode (custom functions)
async def my_model(messages, config):
    accumulated = ""
    for word in ["Hello", "world"]:
        accumulated += word + " "
        yield accumulated  # ← Still yields accumulated
    
chatbot = mo.ui.chat(my_model)
```

### Option 2: Breaking Change to Delta-Only

**Pros**:
- Clean implementation
- Single code path
- Aligns with standards

**Cons**:
- Breaks existing custom streaming functions
- Requires migration guide
- Not backward compatible

#### Implementation

```python
async def _handle_streaming_response(self, response: Any) -> str:
    """Handle streaming from generators that yield deltas."""
    message_id = str(uuid.uuid4())
    accumulated_text = ""

    if inspect.isasyncgen(response):
        async for delta in response:
            delta_str = str(delta)
            accumulated_text += delta_str  # ← Always accumulate
            
            self._send_message({
                "type": "stream_chunk",
                "message_id": message_id,
                "content": accumulated_text,
                "is_final": False,
            }, buffers=None)
```

#### Migration Guide

```python
# Old (pre-0.x.x)
async def my_model(messages, config):
    accumulated = ""
    for word in ["Hello", "world"]:
        accumulated += word + " "
        yield accumulated  # ← Yielded accumulated

# New (0.x.x+)
async def my_model(messages, config):
    for word in ["Hello", "world"]:
        yield word + " "  # ← Yield deltas directly
```

### Option 3: Dual Protocol (Advanced)

Send both delta and accumulated in the protocol:

```python
self._send_message({
    "type": "stream_chunk",
    "message_id": message_id,
    "delta": delta,              # ← New: just the delta
    "content": accumulated_text, # ← Legacy: full text
    "is_final": False,
})
```

**Pros**:
- Frontend can choose rendering strategy
- Most flexible
- Enables advanced UX (typewriter effects, etc.)

**Cons**:
- Bandwidth overhead (sends both)
- More complex protocol

---

## Testing Strategy

### Unit Tests

```python
# tests/_plugins/test_chat.py

async def test_delta_streaming_mode():
    """Test that delta mode accumulates properly."""
    
    async def delta_generator():
        yield "Hello"
        yield " "
        yield "world"
    
    chat = mo.ui.chat(delta_generator)
    
    # Mock _send_message to capture chunks
    chunks = []
    original_send = chat._send_message
    chat._send_message = lambda msg, **kw: chunks.append(msg)
    
    result = await chat._handle_streaming_response(
        delta_generator(), 
        is_delta_mode=True
    )
    
    assert result == "Hello world"
    assert chunks[0]["content"] == "Hello"
    assert chunks[1]["content"] == "Hello "
    assert chunks[2]["content"] == "Hello world"

async def test_accumulated_streaming_mode():
    """Test that legacy mode works as before."""
    
    async def accumulated_generator():
        yield "Hello"
        yield "Hello "
        yield "Hello world"
    
    chat = mo.ui.chat(accumulated_generator)
    
    chunks = []
    chat._send_message = lambda msg, **kw: chunks.append(msg)
    
    result = await chat._handle_streaming_response(
        accumulated_generator(),
        is_delta_mode=False
    )
    
    assert result == "Hello world"
    assert chunks[0]["content"] == "Hello"
    assert chunks[1]["content"] == "Hello "
    assert chunks[2]["content"] == "Hello world"
```

### E2E Tests

```python
# frontend/e2e-tests/chat-streaming.spec.ts

test('delta streaming displays correctly', async ({ page }) => {
  await page.goto('/examples/ai/chat/openai_example.py');
  
  await page.fill('[data-testid="chat-input"]', 'Hello');
  await page.click('[data-testid="chat-send"]');
  
  // Wait for streaming to start
  await page.waitForSelector('[data-streaming="true"]');
  
  // Verify partial content appears
  await expect(page.locator('[data-role="assistant"]')).toContainText('Hello');
  
  // Wait for streaming to complete
  await page.waitForSelector('[data-streaming="false"]');
  
  // Verify full content
  const content = await page.locator('[data-role="assistant"]').textContent();
  expect(content.length).toBeGreaterThan(5);
});
```

---

## Performance Impact

### Current (Accumulated)

For a 1000-word response:
- Bytes sent: ~500KB
- Network requests: 1000 SSE events
- Frontend updates: 1000 re-renders

### Proposed (Delta)

For a 1000-word response:
- Bytes sent: ~5KB (just the words)
- Network requests: 1000 SSE events (same)
- Frontend updates: 1000 re-renders (same, but lighter)

**Result**: ~99% reduction in streaming bandwidth

---

## Backwards Compatibility

### Option 1 (Recommended)

✅ Fully backward compatible
- Existing custom functions continue to work
- New `mo.ai.llm` models use delta mode automatically
- No breaking changes

### Option 2 (Breaking)

❌ Not backward compatible
- Requires v1.0 or major version bump
- All custom streaming functions must migrate
- Needs comprehensive migration guide

### Option 3 (Dual Protocol)

✅ Backward compatible but wasteful
- Existing code works
- New code can optimize
- Temporary solution until v2.0

---

## Recommendation

**Implement Option 1: Add Delta Mode with Auto-Detection**

**Timeline**:
1. **Phase 1 (v0.x.x)**: Add delta mode with auto-detection
   - Detect `ChatModel` instances
   - Maintain legacy behavior for custom functions
   - Add tests and documentation
   
2. **Phase 2 (v0.x+1.x)**: Encourage migration
   - Add deprecation warnings for accumulated mode
   - Provide migration guide
   - Add examples

3. **Phase 3 (v1.0.0)**: Make delta mode default
   - Breaking change: All generators expected to yield deltas
   - Remove accumulated mode
   - Clean up code

**Immediate Benefits**:
- ✅ No breaking changes
- ✅ OpenAI/Anthropic examples work efficiently
- ✅ Aligns with AI SDK standards
- ✅ Better developer experience

**Migration Path**:
- ✅ Clear upgrade path
- ✅ Gradual adoption
- ✅ Time to update custom code

---

## Additional Considerations

### 1. Documentation

Need to update:
- `docs/api/inputs/chat.md`
- `examples/ai/chat/streaming_custom.py`
- Add note about delta vs accumulated modes
- Migration guide for custom functions

### 2. Type Hints

```python
from typing import AsyncGenerator, Literal

StreamingMode = Literal["delta", "accumulated"]

def __init__(
    self,
    model: Callable[[list[ChatMessage], ChatModelConfig], object],
    *,
    streaming_mode: Optional[StreamingMode] = None,  # None = auto-detect
    ...
)
```

### 3. Error Messages

```python
if is_delta_mode:
    # Helpful error if user mixes modes
    if len(accumulated_text) > len(delta) * 100:
        LOGGER.warning(
            "Stream appears to be yielding accumulated text in delta mode. "
            "Set streaming_mode='accumulated' or yield only deltas."
        )
```

### 4. Integration with AI Completions

Align `chat.py` streaming with `providers.py` streaming:

```python
# Reuse the same streaming logic
from marimo._server.ai.providers import CompletionProvider

class chat(UIElement):
    async def _handle_streaming_response(self, response: Any) -> str:
        # Delegate to CompletionProvider's stream handler
        # This ensures consistency across all AI features
        ...
```

---

## Conclusion

Marimo's current accumulated streaming pattern is non-standard and inefficient. By adopting delta-based streaming (Option 1), we can:

1. **Align with industry standards** (OpenAI, Anthropic, AI SDK)
2. **Improve efficiency** (99% bandwidth reduction)
3. **Maintain backward compatibility** (auto-detection)
4. **Simplify developer experience** (pass-through streaming)

The implementation is straightforward and can be done incrementally without breaking existing code.

**Next Steps**:
1. Implement delta mode detection in `chat.py`
2. Add `_marimo_uses_deltas` marker to `ChatModel`
3. Add tests for both modes
4. Update documentation and examples
5. Consider similar changes for other streaming features

