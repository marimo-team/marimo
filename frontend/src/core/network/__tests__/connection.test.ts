/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it } from "vitest";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "../../websocket/types";
import { connectionAtom, waitForConnectionOpenIfNotebook } from "../connection";

const NEVER = Symbol("never");

/**
 * Resolves to NEVER if the promise does not settle within a macrotask.
 */
function settledOrNever(promise: Promise<unknown>) {
  return Promise.race([
    promise,
    new Promise((resolve) => setTimeout(() => resolve(NEVER), 0)),
  ]);
}

describe("waitForConnectionOpenIfNotebook", () => {
  afterEach(() => {
    store.set(connectionAtom, { state: WebSocketState.NOT_STARTED });
    store.set(initialModeAtom, undefined);
  });

  it.each(["home", "gallery"] as const)(
    "resolves without a connection in %s mode",
    async (mode) => {
      store.set(initialModeAtom, mode);
      await expect(
        settledOrNever(waitForConnectionOpenIfNotebook()),
      ).resolves.not.toBe(NEVER);
    },
  );

  it("waits for the connection to open in edit mode", async () => {
    store.set(initialModeAtom, "edit");
    const promise = waitForConnectionOpenIfNotebook();
    await expect(settledOrNever(promise)).resolves.toBe(NEVER);

    store.set(connectionAtom, { state: WebSocketState.OPEN });
    await expect(settledOrNever(promise)).resolves.not.toBe(NEVER);
  });
});
