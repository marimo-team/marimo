/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  type ChatMessagePart,
  useMessageQueue,
  validateChatAttachments,
} from "../chat-utils";

function textPart(text: string): ChatMessagePart {
  return { type: "text", text };
}

describe("useMessageQueue", () => {
  it("initializes empty", () => {
    const { result } = renderHook(() => useMessageQueue());
    expect(result.current.messages).toEqual([]);
  });

  it("enqueues messages in order with unique ids", () => {
    const { result } = renderHook(() => useMessageQueue());

    act(() => result.current.enqueue([textPart("first")]));
    act(() => result.current.enqueue([textPart("second")]));

    const [a, b] = result.current.messages;
    expect(a.parts).toEqual([textPart("first")]);
    expect(b.parts).toEqual([textPart("second")]);
    expect(a.id).toBeTypeOf("string");
    expect(a.id).not.toBe(b.id);
  });

  it("flushNext sends the oldest message's parts and dequeues it", () => {
    const { result } = renderHook(() => useMessageQueue());
    const send = vi.fn();

    act(() => result.current.enqueue([textPart("first")]));
    act(() => result.current.enqueue([textPart("second")]));
    act(() => result.current.flushNext(send));

    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith([textPart("first")]);
    expect(result.current.messages).toEqual([
      expect.objectContaining({ parts: [textPart("second")] }),
    ]);
  });

  it("flushNext sees a message enqueued in the same act (before re-render)", () => {
    const { result } = renderHook(() => useMessageQueue());
    const send = vi.fn();

    // Mirrors enqueue + onFinish in the same tick: the ref must be updated
    // synchronously inside enqueue, not only on the next render.
    act(() => {
      result.current.enqueue([textPart("queued while finishing")]);
      result.current.flushNext(send);
    });

    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith([textPart("queued while finishing")]);
    expect(result.current.messages).toEqual([]);
  });

  it("drains sequentially, even across synchronous flushNext calls", () => {
    const { result } = renderHook(() => useMessageQueue());
    const send = vi.fn();

    act(() => result.current.enqueue([textPart("first")]));
    act(() => result.current.enqueue([textPart("second")]));

    // Two flushes in the same act: the ref must stay in sync so the second
    // flush releases the next message rather than re-sending the first.
    act(() => {
      result.current.flushNext(send);
      result.current.flushNext(send);
    });

    expect(send).toHaveBeenNthCalledWith(1, [textPart("first")]);
    expect(send).toHaveBeenNthCalledWith(2, [textPart("second")]);
    expect(result.current.messages).toEqual([]);
  });

  it("preserves multiple enqueues and flushes before React renders", () => {
    const { result } = renderHook(() => useMessageQueue());
    const send = vi.fn();

    act(() => {
      result.current.enqueue([textPart("first")]);
      result.current.enqueue([textPart("second")]);
      result.current.flushNext(send);
      result.current.flushNext(send);
    });

    expect(send).toHaveBeenNthCalledWith(1, [textPart("first")]);
    expect(send).toHaveBeenNthCalledWith(2, [textPart("second")]);
    expect(result.current.messages).toEqual([]);
    expect(result.current.hasQueuedRef.current).toBe(false);
  });

  it("flushNext on an empty queue is a no-op", () => {
    const { result } = renderHook(() => useMessageQueue());
    const send = vi.fn();

    act(() => result.current.flushNext(send));

    expect(send).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
  });

  it("preserves a queued image when the model changes, then sends it after switching back", () => {
    const { result, rerender } = renderHook(
      ({ types }) => {
        const queue = useMessageQueue();
        return {
          ...queue,
          validate: (parts: ChatMessagePart[]) =>
            validateChatAttachments(parts, types),
        };
      },
      { initialProps: { types: ["text/*", "image/png"] } },
    );
    const parts: ChatMessagePart[] = [
      textPart("describe this"),
      {
        type: "file",
        mediaType: "image/png",
        filename: "chart.png",
        url: "data:image/png;base64,aW1hZ2U=",
      },
    ];
    const send = vi.fn();
    act(() => result.current.enqueue(parts));
    const queued = result.current.messages;
    rerender({ types: ["text/*"] });

    act(() => result.current.flushNext(send, result.current.validate));

    expect(send).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual(queued);
    expect(result.current.hasQueuedRef.current).toBe(true);

    rerender({ types: ["text/*", "image/png"] });
    act(() => result.current.flushNext(send, result.current.validate));

    expect(send).toHaveBeenCalledExactlyOnceWith(parts);
    expect(result.current.messages).toEqual([]);
    expect(result.current.hasQueuedRef.current).toBe(false);
  });

  it("rejects images resolved from context for a text-only model", () => {
    expect(
      validateChatAttachments(
        [
          textPart("describe @cell"),
          {
            type: "file",
            mediaType: "image/png",
            filename: "cell.png",
            url: "data:image/png;base64,aW1hZ2U=",
            providerMetadata: { marimo: { contextAttachment: true } },
          },
        ],
        ["text/*"],
      ),
    ).toBe(false);
  });

  it("clear empties the queue", () => {
    const { result } = renderHook(() => useMessageQueue());

    act(() => result.current.enqueue([textPart("first")]));
    act(() => result.current.enqueue([textPart("second")]));
    act(() => result.current.clear());

    expect(result.current.messages).toEqual([]);
    expect(result.current.hasQueuedRef.current).toBe(false);
  });

  it("hasQueuedRef stays in sync when enqueue and flush run in the same act", () => {
    const { result } = renderHook(() => useMessageQueue());
    const send = vi.fn();

    act(() => {
      result.current.enqueue([textPart("first")]);
      result.current.enqueue([textPart("second")]);
    });
    expect(result.current.hasQueuedRef.current).toBe(true);

    act(() => {
      result.current.flushNext(send);
    });
    expect(result.current.hasQueuedRef.current).toBe(true);

    act(() => {
      result.current.flushNext(send);
    });
    expect(result.current.hasQueuedRef.current).toBe(false);
  });
});
