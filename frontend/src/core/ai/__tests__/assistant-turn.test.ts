/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import {
  finishAssistantTurn,
  isAssistantTurnActive,
  resumeAssistantTurn,
} from "../assistant-turn";

const messages: UIMessage[] = [
  {
    id: "reply",
    role: "assistant",
    parts: [
      {
        type: "tool-lookup",
        toolCallId: "call",
        state: "input-available",
        input: {},
      },
    ],
  },
];
const turn = { startedAt: 1_000, ended: false };
const idle = { isLoading: false, hasError: false, messages };

describe("assistant turns", () => {
  it("stays active between requests only for a live turn without an error", () => {
    expect([
      isAssistantTurnActive({ ...idle, turn: null }),
      isAssistantTurnActive({ ...idle, turn }),
      isAssistantTurnActive({ ...idle, turn: { ...turn, ended: true } }),
      isAssistantTurnActive({ ...idle, turn, hasError: true }),
    ]).toEqual([false, true, false, false]);
  });

  it.each([
    { isAbort: true, isError: false },
    { isAbort: false, isError: true },
    { isAbort: false, isError: false },
  ])(
    "records completion timing and ends interrupted turns ($isAbort, $isError)",
    (finish) => {
      const result = finishAssistantTurn({ turn, messages, ...finish });
      expect(result.turn).toEqual({
        startedAt: 1_000,
        ended: finish.isAbort || finish.isError,
      });
      expect(result.messages.at(-1)?.metadata).toEqual({
        startedAt: 1_000,
        finishedAt: expect.any(Number),
        stopped: finish.isAbort,
      });
      expect(turn).toEqual({ startedAt: 1_000, ended: false });
      expect(messages.at(-1)?.metadata).toBeUndefined();
    },
  );

  it("excludes time waiting on approval while retaining prior work", () => {
    expect(
      resumeAssistantTurn(
        {
          id: "reply",
          role: "assistant",
          parts: [],
          metadata: { startedAt: 1_000, finishedAt: 4_000 },
        },
        10_000,
      ),
    ).toEqual({ startedAt: 7_000, ended: false });
    expect(resumeAssistantTurn(undefined, 10_000)).toEqual({
      startedAt: 10_000,
      ended: false,
    });
  });
});
