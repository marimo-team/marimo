/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import { useAssistantTurn } from "../use-assistant-turn";

const awaitingTool: UIMessage[] = [
  { id: "u", role: "user", parts: [{ type: "text", text: "go" }] },
  {
    id: "a",
    role: "assistant",
    parts: [
      {
        type: "tool-lint_notebook",
        toolCallId: "call",
        state: "input-available",
        input: {},
      },
    ],
  },
];

function setup() {
  return renderHook(() => useAssistantTurn());
}

const idle = { isLoading: false, hasError: false, messages: awaitingTool };

describe("useAssistantTurn", () => {
  it("stays active between requests while a tool is still running", () => {
    const { result } = setup();
    expect(result.current.isActive(idle)).toBe(false);
    act(() => result.current.start());
    expect(result.current.isActive(idle)).toBe(true);
    expect(result.current.startedAt).toEqual(expect.any(Number));
  });

  it("ends on stop, error, or chat switch", () => {
    const { result } = setup();
    act(() => result.current.start());
    act(() => {
      result.current.finish(awaitingTool, { isAbort: true, isError: false });
    });
    expect(result.current.isActive(idle)).toBe(false);

    act(() => result.current.start());
    act(() => {
      result.current.finish(awaitingTool, { isAbort: false, isError: true });
    });
    expect(result.current.isActive(idle)).toBe(false);

    act(() => result.current.start());
    expect(result.current.isActive({ ...idle, hasError: true })).toBe(false);

    act(() => result.current.reset());
    expect(result.current.isActive(idle)).toBe(false);
    expect(result.current.startedAt).toBeNull();
  });

  it("stamps the turn's start on the reply", () => {
    const { result } = setup();
    act(() => result.current.start());
    const [, reply] = result.current.finish(awaitingTool, {
      isAbort: false,
      isError: false,
    });
    expect(reply.metadata).toMatchObject({
      startedAt: result.current.startedAt,
    });
  });

  it("excludes time spent waiting on an approval", () => {
    const reply: UIMessage = {
      id: "a",
      role: "assistant",
      parts: [],
      metadata: { startedAt: 1_000, finishedAt: 4_000 },
    };
    const { result } = setup();
    act(() => result.current.resume(reply));
    expect(Date.now() - (result.current.startedAt ?? 0)).toBeGreaterThanOrEqual(
      3_000,
    );
    expect(Date.now() - (result.current.startedAt ?? 0)).toBeLessThan(4_000);
  });

  it("stops auto-continuing once the user stops the turn", () => {
    const { result } = setup();
    act(() => result.current.start());
    act(() => result.current.stop());
    expect(result.current.hasEnded).toBe(true);
    expect(result.current.isActive(idle)).toBe(false);
  });
});
