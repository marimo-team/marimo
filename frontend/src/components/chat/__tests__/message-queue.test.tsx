/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { type ChatMessagePart, useMessageQueue } from "../chat-utils";

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

  it("flushNext on an empty queue is a no-op", () => {
    const { result } = renderHook(() => useMessageQueue());
    const send = vi.fn();

    act(() => result.current.flushNext(send));

    expect(send).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
  });

  it("clear empties the queue", () => {
    const { result } = renderHook(() => useMessageQueue());

    act(() => result.current.enqueue([textPart("first")]));
    act(() => result.current.enqueue([textPart("second")]));
    act(() => result.current.clear());

    expect(result.current.messages).toEqual([]);
  });
});
