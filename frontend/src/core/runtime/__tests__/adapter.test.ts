/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { islandsInitializedAtom } from "../../islands/state";
import { kernelStateAtom } from "../../kernel/state";
import { connectionAtom } from "../../network/connection";
import { wasmInitStateAtom } from "../../wasm/state";
import { WebSocketState } from "../../websocket/types";
import {
  canRunCellsAtom,
  islandsAdapter,
  remoteAdapter,
  runtimeAdapterAtom,
  staticAdapter,
  wasmAdapter,
} from "../adapter";

describe("wasmAdapter", () => {
  it("reports connecting with the progress label while loading", () => {
    const store = createStore();
    store.set(wasmInitStateAtom, {
      kind: "loading",
      message: "Loading Pyodide…",
    });
    expect(store.get(wasmAdapter.state)).toEqual({
      kind: "connecting",
      progress: { label: "Loading Pyodide…" },
    });
  });

  it("reports ready when initialized", () => {
    const store = createStore();
    store.set(wasmInitStateAtom, { kind: "ready" });
    expect(store.get(wasmAdapter.state)).toEqual({ kind: "ready" });
  });

  it("exposes the real error message on failure", () => {
    const store = createStore();
    store.set(wasmInitStateAtom, {
      kind: "error",
      message: "ImportError: numpy",
    });
    expect(store.get(wasmAdapter.state)).toEqual({
      kind: "failed",
      error: { message: "ImportError: numpy", errorKind: "init" },
    });
  });
});

describe("remoteAdapter", () => {
  it.each([
    [{ state: WebSocketState.OPEN }, { kind: "ready" }],
    [
      { state: WebSocketState.CONNECTING },
      { kind: "connecting", progress: { label: "Connecting…" } },
    ],
    [
      { state: WebSocketState.NOT_STARTED },
      { kind: "connecting", progress: { label: "Not connected" } },
    ],
  ] as const)("maps %j to %j", (conn, expected) => {
    const store = createStore();
    store.set(connectionAtom, conn as never);
    expect(store.get(remoteAdapter.state)).toEqual(expected);
  });

  it("surfaces the close reason when closed", () => {
    const store = createStore();
    store.set(connectionAtom, {
      state: WebSocketState.CLOSED,
      code: "KERNEL_DISCONNECTED",
      reason: "Kernel went away",
    });
    expect(store.get(remoteAdapter.state)).toEqual({
      kind: "failed",
      error: { message: "Kernel went away", errorKind: "runtime" },
    });
  });
});

describe("staticAdapter", () => {
  it("is always ready", () => {
    const store = createStore();
    expect(store.get(staticAdapter.state)).toEqual({ kind: "ready" });
  });

  it("advertises no capabilities", () => {
    expect(staticAdapter.capabilities).toEqual({
      canHealthCheck: false,
      canShutdown: false,
      canRestart: false,
      supportsLsp: false,
    });
  });
});

describe("islandsAdapter", () => {
  it("is connecting before islands report initialization", () => {
    const store = createStore();
    store.set(islandsInitializedAtom, false);
    expect(store.get(islandsAdapter.state)).toEqual({
      kind: "connecting",
      progress: { label: "Initializing islands…" },
    });
  });

  it("is ready once islands initialize", () => {
    const store = createStore();
    store.set(islandsInitializedAtom, true);
    expect(store.get(islandsAdapter.state)).toEqual({ kind: "ready" });
  });

  it("surfaces the error string when islands fail", () => {
    const store = createStore();
    store.set(islandsInitializedAtom, "wheel download failed");
    expect(store.get(islandsAdapter.state)).toEqual({
      kind: "failed",
      error: { message: "wheel download failed", errorKind: "init" },
    });
  });
});

describe("canRunCellsAtom", () => {
  it("is false on a remote adapter until kernel acks", () => {
    const store = createStore();
    // Default adapter in test env is remote.
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    expect(store.get(canRunCellsAtom)).toBe(false);

    store.set(kernelStateAtom, { isInstantiated: true, error: null });
    expect(store.get(canRunCellsAtom)).toBe(true);
  });

  it("is true on WASM as soon as the adapter is ready (no separate kernel ack)", () => {
    const store = createStore();
    store.set(runtimeAdapterAtom, wasmAdapter);
    store.set(wasmInitStateAtom, { kind: "loading", message: "…" });
    expect(store.get(canRunCellsAtom)).toBe(false);

    store.set(wasmInitStateAtom, { kind: "ready" });
    expect(store.get(canRunCellsAtom)).toBe(true);
  });

  it("is always false on a static notebook", () => {
    const store = createStore();
    store.set(runtimeAdapterAtom, staticAdapter);
    expect(store.get(canRunCellsAtom)).toBe(false);
  });

  it("is true on islands once initialized", () => {
    const store = createStore();
    store.set(runtimeAdapterAtom, islandsAdapter);
    store.set(islandsInitializedAtom, false);
    expect(store.get(canRunCellsAtom)).toBe(false);

    store.set(islandsInitializedAtom, true);
    expect(store.get(canRunCellsAtom)).toBe(true);
  });
});
