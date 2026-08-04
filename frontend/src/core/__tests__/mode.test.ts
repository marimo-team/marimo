/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import { runDuringPresentMode, viewStateAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";

const requestAnimationFrameMock = vi.fn((callback: FrameRequestCallback) => {
  callback(0);
  return 0;
});

async function runAfterRender(fn: () => void | Promise<void>): Promise<void> {
  const result = runDuringPresentMode(fn);
  await vi.runAllTimersAsync();
  return result;
}

describe("runDuringPresentMode", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("requestAnimationFrame", requestAnimationFrameMock);
    requestAnimationFrameMock.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("runs in present mode and restores the captured view state", async () => {
    const state = { mode: "edit" as const, cellAnchor: CellId.create() };
    store.set(viewStateAtom, state);

    await runAfterRender(() => {
      expect(store.get(viewStateAtom)).toEqual({
        ...state,
        mode: "present",
      });
    });

    expect(store.get(viewStateAtom)).toEqual(state);
    expect(requestAnimationFrameMock).toHaveBeenCalledTimes(2);
  });

  it("restores the captured view state when the callback rejects", async () => {
    const state = { mode: "edit" as const, cellAnchor: CellId.create() };
    const error = new Error("capture failed");
    store.set(viewStateAtom, state);

    const result = runDuringPresentMode(() => Promise.reject(error));
    const rejection = expect(result).rejects.toBe(error);
    await vi.runAllTimersAsync();
    await rejection;

    expect(store.get(viewStateAtom)).toEqual(state);
  });

  it("runs directly when already in present mode", async () => {
    const state = { mode: "present" as const, cellAnchor: CellId.create() };
    store.set(viewStateAtom, state);

    await runDuringPresentMode(() => {
      expect(store.get(viewStateAtom)).toEqual(state);
    });

    expect(store.get(viewStateAtom)).toEqual(state);
    expect(requestAnimationFrameMock).not.toHaveBeenCalled();
  });

  it.each(["read", "home", "gallery"] as const)(
    "runs directly without changing %s mode",
    async (mode) => {
      const state = { mode, cellAnchor: CellId.create() };
      store.set(viewStateAtom, state);

      await runDuringPresentMode(() => {
        expect(store.get(viewStateAtom)).toEqual(state);
      });

      expect(store.get(viewStateAtom)).toEqual(state);
      expect(requestAnimationFrameMock).not.toHaveBeenCalled();
    },
  );
});
