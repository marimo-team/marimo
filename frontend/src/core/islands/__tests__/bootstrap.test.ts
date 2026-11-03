/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookTransport } from "@marimo-team/client";
import { createStore } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import {
  fakeBackend,
  fixtureMessages,
} from "@/core/notebook/replica/__tests__/fixtures";
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
      notebookBackend: fakeBackend(),
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

describe("initializeIslands document", () => {
  afterEach(vi.restoreAllMocks);

  it("fills the notebook's cells from the managed session's host document", async () => {
    const root = document.createElement("div");
    root.innerHTML =
      '<marimo-island data-app-id="app-1" data-reactive="true"></marimo-island>';
    let handlers: Parameters<NotebookTransport>[1] | undefined;
    const transport: NotebookTransport = (_attempt, opened) =>
      new Promise(() => {
        handlers = opened;
        opened.open();
      });
    const bridge = {
      consumeNotifications: vi.fn(),
      sendComponentValues: vi.fn(),
      notebookBackend: fakeBackend({ transport }),
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
    await vi.waitFor(() => expect(handlers).toBeDefined());
    for (const message of fixtureMessages("notebook-events.sse")) {
      handlers?.message(message);
    }

    const notebook = store.get(notebookAtom);
    expect(notebook.cellIds.inOrderIds).toEqual(["c1", "c3", "k7f2"]);
    expect(notebook.cellData[cellId("c3")].code).toBe("x = 21");
    expect(notebook.cellRuntime[cellId("c3")]).toBeDefined();

    handlers?.message({ event: "reset", data: {} });
    expect(store.get(notebookAtom).cellIds.inOrderIds).toEqual([
      "c1",
      "c3",
      "k7f2",
    ]);
  });
});
