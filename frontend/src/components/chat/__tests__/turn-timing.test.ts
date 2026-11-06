/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import { formatDuration, getTurnTiming, withTurnTiming } from "../turn-timing";

const user: UIMessage = { id: "u", role: "user", parts: [] };
const assistant = (metadata?: unknown): UIMessage => ({
  id: "a",
  role: "assistant",
  parts: [],
  metadata,
});

describe("withTurnTiming", () => {
  it("stamps the turn start and finish on the trailing assistant message", () => {
    const [, stamped] = withTurnTiming(
      [user, assistant()],
      { startedAt: 100, stopped: false },
      500,
    );
    expect(getTurnTiming(stamped)).toEqual({
      startedAt: 100,
      finishedAt: 500,
      stopped: false,
    });
  });

  it("keeps the original start across follow-up requests in the same turn", () => {
    const first = withTurnTiming(
      [user, assistant({ other: 1 })],
      { startedAt: 100, stopped: false },
      500,
    );
    const [, stamped] = withTurnTiming(
      first,
      { startedAt: 400, stopped: true },
      900,
    );
    expect(stamped.metadata).toEqual({
      other: 1,
      startedAt: 100,
      finishedAt: 900,
      stopped: true,
    });
  });

  it("leaves messages untouched without an assistant reply or start time", () => {
    const pending = [user];
    const turn = { startedAt: 100, stopped: false };
    expect(withTurnTiming(pending, turn, 500)).toBe(pending);
    const unknownStart = [user, assistant()];
    expect(
      withTurnTiming(unknownStart, { ...turn, startedAt: null }, 500),
    ).toBe(unknownStart);
  });
});

describe("formatDuration", () => {
  it.each([
    [200, "1s"],
    [8_400, "8s"],
    [60_000, "1m"],
    [65_000, "1m 5s"],
    [3_600_000, "1h"],
    [3_780_000, "1h 3m"],
  ])("%d ms → %s", (ms, expected) => {
    expect(formatDuration(ms)).toBe(expected);
  });
});
