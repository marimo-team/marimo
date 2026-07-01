/* Copyright 2026 Marimo. All rights reserved. */

import { type Atom, atom } from "jotai";
import { kernelStateAtom } from "../kernel/state";
import { islandsInitializedAtom } from "../islands/state";
import { isIslands } from "../islands/utils";
import { connectionAtom } from "../network/connection";
import { isStaticNotebook } from "../static/static-state";
import { wasmInitStateAtom } from "../wasm/state";
import { isWasm } from "../wasm/utils";
import { WebSocketState } from "../websocket/types";

export type RuntimeKind = "wasm" | "remote" | "static" | "islands";

export type AdapterState =
  | { kind: "connecting"; progress?: { label: string; percent?: number } }
  | { kind: "ready" }
  | {
      kind: "failed";
      error: { message: string; errorKind: "init" | "runtime" };
    };

export interface RuntimeCapabilities {
  canHealthCheck: boolean;
  canShutdown: boolean;
  canRestart: boolean;
  supportsLsp: boolean;
}

/** Runtimes with no server-side kernel to manage (wasm, static, islands). */
const NO_CAPABILITIES: RuntimeCapabilities = {
  canHealthCheck: false,
  canShutdown: false,
  canRestart: false,
  supportsLsp: false,
};

/**
 * One adapter per runtime so consumers don't branch on `isWasm()` /
 * `isStaticNotebook()` / `isIslands()` at the call site.
 */
export interface RuntimeAdapter {
  readonly kind: RuntimeKind;
  /** Short label suitable for status pills, e.g. "Kernel", "Pyodide". */
  readonly label: string;
  readonly capabilities: RuntimeCapabilities;
  state: Atom<AdapterState>;
}

// --- WASM ------------------------------------------------------------------

const wasmStateAtom = atom<AdapterState>((get) => {
  const s = get(wasmInitStateAtom);
  switch (s.kind) {
    case "loading":
      return { kind: "connecting", progress: { label: s.message } };
    case "ready":
      return { kind: "ready" };
    case "error":
      return {
        kind: "failed",
        error: { message: s.message, errorKind: "init" },
      };
  }
});

export const wasmAdapter: RuntimeAdapter = {
  kind: "wasm",
  label: "Pyodide",
  capabilities: NO_CAPABILITIES,
  state: wasmStateAtom,
};

// --- Remote ----------------------------------------------------------------

const remoteStateAtom = atom<AdapterState>((get) => {
  const conn = get(connectionAtom);
  switch (conn.state) {
    case WebSocketState.OPEN:
      return { kind: "ready" };
    case WebSocketState.CONNECTING:
      return { kind: "connecting", progress: { label: "Connecting…" } };
    case WebSocketState.NOT_STARTED:
      return { kind: "connecting", progress: { label: "Not connected" } };
    case WebSocketState.CLOSING:
    case WebSocketState.CLOSED:
      return {
        kind: "failed",
        error: {
          message:
            conn.state === WebSocketState.CLOSED
              ? conn.reason
              : "Disconnecting",
          errorKind: "runtime",
        },
      };
  }
});

export const remoteAdapter: RuntimeAdapter = {
  kind: "remote",
  label: "Kernel",
  capabilities: {
    canHealthCheck: true,
    canShutdown: true,
    canRestart: true,
    supportsLsp: true,
  },
  state: remoteStateAtom,
};

// --- Static ----------------------------------------------------------------

const staticStateAtom = atom<AdapterState>({ kind: "ready" });

export const staticAdapter: RuntimeAdapter = {
  kind: "static",
  label: "Static",
  capabilities: NO_CAPABILITIES,
  state: staticStateAtom,
};

// --- Islands ---------------------------------------------------------------

const islandsStateAtom = atom<AdapterState>((get) => {
  const status = get(islandsInitializedAtom);
  if (status === true) {
    return { kind: "ready" };
  }
  if (typeof status === "string") {
    return {
      kind: "failed",
      error: { message: status, errorKind: "init" },
    };
  }
  return {
    kind: "connecting",
    progress: { label: "Initializing islands…" },
  };
});

export const islandsAdapter: RuntimeAdapter = {
  kind: "islands",
  label: "Islands",
  capabilities: NO_CAPABILITIES,
  state: islandsStateAtom,
};

function selectAdapter(): RuntimeAdapter {
  if (isStaticNotebook()) {
    return staticAdapter;
  }
  if (isIslands()) {
    return islandsAdapter;
  }
  if (isWasm()) {
    return wasmAdapter;
  }
  return remoteAdapter;
}

/** Picked once at mount; the choice doesn't change after page load. */
export const runtimeAdapterAtom = atom<RuntimeAdapter>(selectAdapter());

/**
 * Remote runtimes require both the WS to be open *and* the kernel to have
 * ack'd instantiation. WASM/islands have no separate kernel handshake.
 * Static notebooks never run cells.
 */
export const canRunCellsAtom = atom<boolean>((get) => {
  const adapter = get(runtimeAdapterAtom);
  if (get(adapter.state).kind !== "ready") {
    return false;
  }
  if (adapter.kind === "static") {
    return false;
  }
  if (adapter.kind === "remote") {
    return get(kernelStateAtom).isInstantiated;
  }
  return true;
});
