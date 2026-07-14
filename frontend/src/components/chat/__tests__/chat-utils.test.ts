/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import { hasPendingToolCalls, shouldFlushQueue } from "../chat-utils";

/**
 * `hasPendingToolCalls` powers `sendAutomaticallyWhen` in `mo.ui.chat`:
 * returns true only when the last assistant message *ends* with a tool
 * call in a ready-to-round-trip state. Any trailing non-tool part (text,
 * file, source-*, reasoning, data-*, new step-start) means the assistant
 * has already answered and we leave the next turn to the user. The
 * approval flow relies on this firing for `approval-responded`.
 */

const userMessage = (text: string): UIMessage => ({
  id: `user-${text}`,
  role: "user",
  parts: [{ type: "text", text }],
});

const assistantToolMessage = (
  parts: UIMessage["parts"],
  id = "assistant-1",
): UIMessage => ({
  id,
  role: "assistant",
  parts,
});

describe("hasPendingToolCalls", () => {
  it("returns false when there are no messages", () => {
    expect(hasPendingToolCalls([])).toBe(false);
  });

  it("returns false when the last message is a user message", () => {
    expect(hasPendingToolCalls([userMessage("hi")])).toBe(false);
  });

  it("returns false when the last assistant message has no tool parts", () => {
    expect(
      hasPendingToolCalls([
        userMessage("hi"),
        assistantToolMessage([{ type: "text", text: "hello!" }]),
      ]),
    ).toBe(false);
  });

  it("returns false while a tool is still streaming or awaiting approval", () => {
    expect(
      hasPendingToolCalls([
        userMessage("delete it"),
        assistantToolMessage([
          {
            type: "tool-delete_file",
            toolCallId: "call-1",
            state: "approval-requested",
            input: { path: "secrets.env" },
            approval: { id: "approval-1" },
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(false);
  });

  it("returns true when the user has responded to an approval request", () => {
    // The chat must auto-resume as soon as Approve/Deny is clicked.
    expect(
      hasPendingToolCalls([
        userMessage("delete it"),
        assistantToolMessage([
          {
            type: "tool-delete_file",
            toolCallId: "call-1",
            state: "approval-responded",
            input: { path: "secrets.env" },
            approval: { id: "approval-1", approved: true },
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(true);
  });

  it("returns true when a tool reached a terminal output state", () => {
    expect(
      hasPendingToolCalls([
        userMessage("run it"),
        assistantToolMessage([
          {
            type: "tool-run_query",
            toolCallId: "call-1",
            state: "output-available",
            input: { sql: "select 1" },
            output: 1,
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(true);
  });

  it("returns false when only some tool calls are ready", () => {
    expect(
      hasPendingToolCalls([
        userMessage("two things"),
        assistantToolMessage([
          {
            type: "tool-first",
            toolCallId: "call-1",
            state: "output-available",
            input: {},
            output: 1,
          } as unknown as UIMessage["parts"][number],
          {
            type: "tool-second",
            toolCallId: "call-2",
            state: "input-available",
            input: {},
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(false);
  });

  it("returns false once the assistant has appended text after the tool result", () => {
    expect(
      hasPendingToolCalls([
        userMessage("run it"),
        assistantToolMessage([
          {
            type: "tool-run_query",
            toolCallId: "call-1",
            state: "output-available",
            input: {},
            output: 1,
          } as unknown as UIMessage["parts"][number],
          { type: "text", text: "The query returned 1." },
        ]),
      ]),
    ).toBe(false);
  });

  it("returns false when a file part trails the completed tool call", () => {
    // Regression: tool → text → file used to loop because only trailing
    // text counted as "the assistant has answered".
    expect(
      hasPendingToolCalls([
        userMessage("show me Starry Night"),
        assistantToolMessage([
          { type: "step-start" },
          {
            type: "tool-search_artwork",
            toolCallId: "call-1",
            state: "output-available",
            input: { artist: "Van Gogh" },
            output: { title: "The Starry Night" },
          } as unknown as UIMessage["parts"][number],
          { type: "text", text: "Here is the painting:" },
          {
            type: "file",
            mediaType: "image/jpeg",
            url: "https://example.com/starry-night.jpg",
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(false);
  });

  it("returns false when a source-url part trails the completed tool call", () => {
    expect(
      hasPendingToolCalls([
        userMessage("cite your sources"),
        assistantToolMessage([
          {
            type: "tool-web_search",
            toolCallId: "call-1",
            state: "output-available",
            input: { q: "marimo notebook" },
            output: "found",
          } as unknown as UIMessage["parts"][number],
          { type: "text", text: "marimo is a reactive notebook." },
          {
            type: "source-url",
            sourceId: "src-1",
            url: "https://marimo.io",
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(false);
  });

  it("returns false when a reasoning part trails the completed tool call", () => {
    expect(
      hasPendingToolCalls([
        userMessage("explain"),
        assistantToolMessage([
          {
            type: "tool-lookup",
            toolCallId: "call-1",
            state: "output-available",
            input: {},
            output: 1,
          } as unknown as UIMessage["parts"][number],
          {
            type: "reasoning",
            text: "Now I'll summarize.",
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(false);
  });

  it("returns false when a new step-start follows the completed tool call", () => {
    expect(
      hasPendingToolCalls([
        userMessage("multi-step"),
        assistantToolMessage([
          { type: "step-start" },
          {
            type: "tool-run_query",
            toolCallId: "call-1",
            state: "output-available",
            input: {},
            output: 1,
          } as unknown as UIMessage["parts"][number],
          { type: "step-start" },
        ]),
      ]),
    ).toBe(false);
  });

  it("ignores providerExecuted tools", () => {
    // Provider-side tools are resolved by the model, not the runtime, so
    // they must not drive an auto-resume.
    expect(
      hasPendingToolCalls([
        userMessage("hi"),
        assistantToolMessage([
          {
            type: "tool-web_search",
            toolCallId: "call-1",
            state: "output-available",
            input: {},
            output: 1,
            providerExecuted: true,
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(false);
  });

  it("returns true for dynamic-tool parts in a terminal state", () => {
    // `dynamic-tool` parts must drive auto-resume alongside `tool-*`.
    expect(
      hasPendingToolCalls([
        userMessage("run it"),
        assistantToolMessage([
          {
            type: "dynamic-tool",
            toolName: "run_query",
            toolCallId: "call-1",
            state: "output-available",
            input: {},
            output: 1,
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(true);
  });
});

describe("shouldFlushQueue", () => {
  it("flushes when the turn completed without error or pending tools", () => {
    expect(
      shouldFlushQueue({ isError: false, hasPendingToolCalls: false }),
    ).toBe(true);
  });

  it("does not flush on error", () => {
    expect(
      shouldFlushQueue({ isError: true, hasPendingToolCalls: false }),
    ).toBe(false);
  });

  it("does not flush while a tool round-trip is still pending", () => {
    expect(
      shouldFlushQueue({ isError: false, hasPendingToolCalls: true }),
    ).toBe(false);
  });

  it("does not flush on error even when tools are also pending", () => {
    expect(shouldFlushQueue({ isError: true, hasPendingToolCalls: true })).toBe(
      false,
    );
  });
});
