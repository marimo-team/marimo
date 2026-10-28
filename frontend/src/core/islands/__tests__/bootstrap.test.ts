/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RuntimeState } from "@/core/kernel/RuntimeState";
import { initializeIslands } from "../bootstrap";
import type { IslandsPyodideBridge } from "../bridge";
import { islandsHydratedAtom, islandsPendingInitialRunsAtom } from "../state";
import type { NotificationMessage } from "@/core/kernel/messages";

type Consumer = (
  notification: NotificationMessage,
  sessionGeneration: number,
) => void;

const completedRun = {
  op: "completed-run",
  run_id: null,
} as NotificationMessage;

describe("initializeIslands", () => {
  afterEach(vi.restoreAllMocks);

  it("waits for each initial session to complete", async () => {
    const root = document.createElement("div");
    root.innerHTML =
      '<marimo-island data-app-id="app-1" data-reactive="true"></marimo-island>';

    let consumeMessage: Consumer | undefined;
    const bridge = {
      consumeNotifications: (consumer: Consumer) => {
        consumeMessage = consumer;
      },
      sendComponentValues: vi.fn(),
    } as unknown as IslandsPyodideBridge;
    const store = createStore();
    vi.spyOn(RuntimeState.INSTANCE, "start").mockImplementation(
      () => undefined,
    );

    await initializeIslands({
      bridge,
      store,
      root,
      autoInitializePlugins: false,
    });

    expect(store.get(islandsHydratedAtom)).toBe(false);
    store.set(islandsPendingInitialRunsAtom, new Set([1, 2]));

    consumeMessage?.(completedRun, 1);
    expect(store.get(islandsHydratedAtom)).toBe(false);

    consumeMessage?.(completedRun, 1);
    consumeMessage?.(completedRun, 0);
    expect(store.get(islandsHydratedAtom)).toBe(false);

    consumeMessage?.(completedRun, 2);
    expect(store.get(islandsHydratedAtom)).toBe(true);
  });
});
