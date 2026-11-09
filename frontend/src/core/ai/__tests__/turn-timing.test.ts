/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import { getTurnTiming, withTurnTiming } from "../turn-timing";

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

  it("prefers the live turn's start, which moves forward after approvals", () => {
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
      startedAt: 400,
      finishedAt: 900,
      stopped: true,
    });
  });

  it("keeps the stored start when no turn is live", () => {
    const first = withTurnTiming(
      [user, assistant()],
      { startedAt: 100, stopped: false },
      500,
    );
    const [, stamped] = withTurnTiming(
      first,
      { startedAt: null, stopped: false },
      900,
    );
    expect(getTurnTiming(stamped)?.startedAt).toBe(100);
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
