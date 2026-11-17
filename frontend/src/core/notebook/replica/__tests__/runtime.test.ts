/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { runtime } from "../resources/runtime";
import { createNotebookReducer } from "@marimo-team/client";
import { fixtureEvents } from "./fixtures";

const reducer = createNotebookReducer({ runtime });
const snapshot = fixtureEvents("notebook-events.sse");
const confirmed = () => snapshot.reduce(reducer.reduce, reducer.initial);
const current = (state: ReturnType<typeof confirmed>) =>
  state.resources.runtime;
const time = "2026-10-01T09:30:00Z";

describe("runtime resource", () => {
  it("keeps the latest record and clears when that runtime is removed", () => {
    const state = confirmed();
    const running = current(state);
    expect(running?.id).toBe("r1");
    expect(running?.status).toBe("running");

    const terminating = reducer.reduce(state, {
      event: "runtime",
      id: "98",
      data: { runtime: { ...running!, status: "terminating" } },
    });
    expect(current(terminating)?.status).toBe("terminating");
    expect(current(state)?.status).toBe("running");

    const other = reducer.reduce(terminating, {
      event: "runtime.removed",
      id: "99",
      data: { id: "r0", time },
    });
    expect(current(other)).toBe(current(terminating));

    const removed = reducer.reduce(other, {
      event: "runtime.removed",
      id: "100",
      data: { id: "r1", time },
    });
    expect(current(removed)).toBeNull();
    const repeated = reducer.reduce(removed, {
      event: "runtime.removed",
      id: "101",
      data: { id: "r1", time },
    });
    expect(repeated.resources).toBe(removed.resources);
  });

  it("follows a restart to the replacement runtime", () => {
    const state = confirmed();
    const removed = reducer.reduce(state, {
      event: "runtime.removed",
      id: "98",
      data: { id: "r1", time },
    });
    const replacement = {
      ...current(state)!,
      id: "r2",
      status: "starting" as const,
      message: "Starting the kernel",
      marimo_version: null,
      started_at: "2026-10-01T09:31:00Z",
    };
    const starting = reducer.reduce(removed, {
      event: "runtime",
      id: "99",
      data: { runtime: replacement },
    });
    expect(current(starting)).toEqual(replacement);
  });

  it("clears on reset", () => {
    const reset = reducer.reduce(confirmed(), { event: "reset", data: {} });
    expect(current(reset)).toBeNull();
  });
});
