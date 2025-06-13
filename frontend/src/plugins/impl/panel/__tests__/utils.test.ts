/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EventBuffer, extractBuffers, MessageSchema } from "../utils";

describe("MessageSchema", () => {
  it("should validate ACK message", () => {
    const result = MessageSchema.safeParse({ content: { type: "ACK" } });
    expect(result.success).toBe(true);
  });

  it("should validate string message", () => {
    const result = MessageSchema.safeParse({ content: "Hello" });
    expect(result.success).toBe(true);
  });

  it("should reject invalid message", () => {
    const result = MessageSchema.safeParse({ content: { type: "INVALID" } });
    expect(result.success).toBe(false);
  });
});

describe.skip("extractBuffers", () => {
  it("should extract ArrayBuffer and replace with id", () => {
    const buffer = new ArrayBuffer(8);
    const input = { data: buffer };
    const buffers: ArrayBuffer[] = [];

    const result = extractBuffers(input, buffers);

    expect(result).toEqual({ data: { id: 0 } });
    expect(buffers).toEqual([buffer]);
  });

  it("should handle nested objects and arrays", () => {
    const buffer1 = new ArrayBuffer(8);
    const buffer2 = new ArrayBuffer(16);
    const input = {
      nested: {
        array: [1, buffer1, { buf: buffer2 }],
      },
    };
    const buffers: ArrayBuffer[] = [];

    const result = extractBuffers(input, buffers);

    expect(result).toEqual({
      nested: {
        array: [1, { id: 0 }, { buf: { id: 1 } }],
      },
    });
    expect(buffers).toEqual([buffer1, buffer2]);
  });

  it("should handle Map objects", () => {
    const buffer = new ArrayBuffer(8);
    const input = new Map([["key", buffer]]);
    const buffers: ArrayBuffer[] = [];

    const result = extractBuffers(input, buffers);

    expect(result).toEqual({ key: { id: 0 } });
    expect(buffers).toEqual([buffer]);
  });
});

describe("EventBuffer", () => {
  let processEvents: () => void;
  let eventBuffer: EventBuffer<string>;

  beforeEach(() => {
    vi.useFakeTimers();
    processEvents = vi.fn();
    eventBuffer = new EventBuffer(processEvents, 50);
  });

  it("should add events to buffer", () => {
    eventBuffer.add("event1");
    eventBuffer.add("event2");

    expect(eventBuffer.size()).toBe(2);
  });

  it("should process events immediately on first add", () => {
    eventBuffer.add("event1");

    expect(processEvents).toHaveBeenCalledTimes(1);
  });

  it("should block processing for specified duration", () => {
    eventBuffer.add("event1");
    eventBuffer.add("event2");

    expect(processEvents).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(49);
    expect(processEvents).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1);
    expect(processEvents).toHaveBeenCalledTimes(2);
  });

  it("should clear buffer", () => {
    eventBuffer.add("event1");
    eventBuffer.add("event2");
    eventBuffer.clear();

    expect(eventBuffer.size()).toBe(0);
  });

  it("should get and clear buffer", () => {
    eventBuffer.add("event1");
    eventBuffer.add("event2");

    const events = eventBuffer.getAndClear();

    expect(events).toEqual(["event1", "event2"]);
    expect(eventBuffer.size()).toBe(0);
  });
});
