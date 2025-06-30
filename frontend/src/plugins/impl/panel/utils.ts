/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

export const MessageSchema = z.object({
  content: z
    .union([
      z.object({
        type: z.literal("ACK"),
      }),
      z.string(),
    ])
    .nullable(),
});

/**
 * Extracts buffers from a message.
 * This mutates the buffers array.
 */
export function extractBuffers(
  value: unknown,
  buffers: ArrayBuffer[],
): unknown {
  if (Array.isArray(value)) {
    return value.map((v) => extractBuffers(v, buffers));
  }
  if (value instanceof Map) {
    const result: Record<string, unknown> = {};
    for (const [key, v] of value.entries()) {
      result[String(key)] = extractBuffers(v, buffers);
    }
    return result;
  }
  if (
    typeof value === "object" &&
    value !== null &&
    "to_base64" in value &&
    typeof value.to_base64 === "function"
  ) {
    const id = buffers.length;
    buffers.push(value.to_base64());
    return { id };
  }
  if (typeof value === "object" && value !== null) {
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(value)) {
      result[key] = extractBuffers(
        (value as Record<string, unknown>)[key],
        buffers,
      );
    }
    return result;
  }
  return value;
}

export class EventBuffer<T> {
  private buffer: T[] = [];
  private isBlocked = false;
  private timeout: number | null = null;

  constructor(
    private processEvents: () => void,
    private blockDuration = 200,
  ) {}

  add(event: T) {
    this.buffer.push(event);
    this.flush();
  }

  private flush() {
    if (!this.isBlocked) {
      this.processEvents();
      this.block();
    }
  }

  private block() {
    this.isBlocked = true;
    if (this.timeout !== null) {
      clearTimeout(this.timeout);
    }
    this.timeout = globalThis.setTimeout(() => {
      this.isBlocked = false;
      if (this.buffer.length > 0) {
        this.flush();
      }
    }, this.blockDuration);
  }

  size() {
    return this.buffer.length;
  }

  clear() {
    this.buffer = [];
  }

  getAndClear() {
    const events = [...this.buffer];
    this.clear();
    return events;
  }
}
