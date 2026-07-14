/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import {
  hasPendingToolCalls,
  hasUnresolvedToolCalls,
  shouldFlushQueue,
} from "../chat-utils";

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

  it("returns true when the user denied a tool approval", () => {
    expect(
      hasPendingToolCalls([
        userMessage("delete it"),
        assistantToolMessage([
          {
            type: "tool-delete_file",
            toolCallId: "call-1",
            state: "output-denied",
            input: { path: "secrets.env" },
            approval: { id: "approval-1", approved: false },
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

describe("hasUnresolvedToolCalls", () => {
  it("returns false when there are no messages", () => {
    expect(hasUnresolvedToolCalls([])).toBe(false);
  });

  it("returns true while approval is still requested", () => {
    expect(
      hasUnresolvedToolCalls([
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
    ).toBe(true);
  });

  it("returns true while a tool is still running", () => {
    expect(
      hasUnresolvedToolCalls([
        userMessage("run it"),
        assistantToolMessage([
          {
            type: "tool-run_query",
            toolCallId: "call-1",
            state: "input-available",
            input: { sql: "select 1" },
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(true);
  });

  it("returns false once tools are ready to round-trip", () => {
    expect(
      hasUnresolvedToolCalls([
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
    ).toBe(false);
  });

  it("returns false once the user denied a tool approval", () => {
    expect(
      hasUnresolvedToolCalls([
        userMessage("delete it"),
        assistantToolMessage([
          {
            type: "tool-delete_file",
            toolCallId: "call-1",
            state: "output-denied",
            input: { path: "secrets.env" },
            approval: { id: "approval-1", approved: false },
          } as unknown as UIMessage["parts"][number],
        ]),
      ]),
    ).toBe(false);
  });
});

describe("shouldFlushQueue", () => {
  it("flushes when the turn completed without error or pending tools", () => {
    expect(
      shouldFlushQueue({
        isError: false,
        isAbort: false,
        hasPendingToolCalls: false,
        hasUnresolvedToolCalls: false,
      }),
    ).toBe(true);
  });

  it("does not flush on error", () => {
    expect(
      shouldFlushQueue({
        isError: true,
        isAbort: false,
        hasPendingToolCalls: false,
        hasUnresolvedToolCalls: false,
      }),
    ).toBe(false);
  });

  it("does not flush while a tool round-trip is still pending", () => {
    expect(
      shouldFlushQueue({
        isError: false,
        isAbort: false,
        hasPendingToolCalls: true,
        hasUnresolvedToolCalls: false,
      }),
    ).toBe(false);
  });

  it("does not flush while approval is still requested", () => {
    expect(
      shouldFlushQueue({
        isError: false,
        isAbort: false,
        hasPendingToolCalls: false,
        hasUnresolvedToolCalls: true,
      }),
    ).toBe(false);
  });

  it("flushes on abort even when a tool is still streaming", () => {
    expect(
      shouldFlushQueue({
        isError: false,
        isAbort: true,
        hasPendingToolCalls: false,
        hasUnresolvedToolCalls: true,
      }),
    ).toBe(true);
  });

  it("does not flush on abort when the run ended in error", () => {
    expect(
      shouldFlushQueue({
        isError: true,
        isAbort: true,
        hasPendingToolCalls: false,
        hasUnresolvedToolCalls: true,
      }),
    ).toBe(false);
  });

  it("flushes once trailing text is present and tools are resolved", () => {
    const messages = [
      userMessage("run it"),
      assistantToolMessage([
        {
          type: "tool-run_query",
          toolCallId: "call-1",
          state: "output-available",
          input: {},
          output: 1,
        } as unknown as UIMessage["parts"][number],
        { type: "text", text: "Done." },
      ]),
    ];

    expect(
      shouldFlushQueue({
        isError: false,
        isAbort: false,
        hasPendingToolCalls: hasPendingToolCalls(messages),
        hasUnresolvedToolCalls: hasUnresolvedToolCalls(messages),
      }),
    ).toBe(true);
  });

  it("blocks flush while text trails a still-running tool, then allows it after resolution", () => {
    const running = [
      userMessage("run it"),
      assistantToolMessage([
        {
          type: "tool-run_query",
          toolCallId: "call-1",
          state: "input-available",
          input: {},
        } as unknown as UIMessage["parts"][number],
        { type: "text", text: "Running your query..." },
      ]),
    ];
    const resolved = [
      userMessage("run it"),
      assistantToolMessage([
        {
          type: "tool-run_query",
          toolCallId: "call-1",
          state: "output-available",
          input: {},
          output: 1,
        } as unknown as UIMessage["parts"][number],
        { type: "text", text: "Running your query..." },
      ]),
    ];

    expect(
      shouldFlushQueue({
        isError: false,
        isAbort: false,
        hasPendingToolCalls: hasPendingToolCalls(running),
        hasUnresolvedToolCalls: hasUnresolvedToolCalls(running),
      }),
    ).toBe(false);
    expect(
      shouldFlushQueue({
        isError: false,
        isAbort: false,
        hasPendingToolCalls: hasPendingToolCalls(resolved),
        hasUnresolvedToolCalls: hasUnresolvedToolCalls(resolved),
      }),
    ).toBe(true);
  });

  it("does not flush on error even when tools are also pending", () => {
    expect(
      shouldFlushQueue({
        isError: true,
        isAbort: false,
        hasPendingToolCalls: true,
        hasUnresolvedToolCalls: true,
      }),
    ).toBe(false);
  });
});
