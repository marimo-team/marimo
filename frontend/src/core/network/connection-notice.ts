/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { sandboxAtom, sandboxSyncAtom } from "@/core/packages/sandbox-state";
import {
  type ConnectionPhase,
  WebSocketClosedReason,
  WebSocketState,
} from "@/core/websocket/types";
import { connectionAtom } from "./connection";

export interface ConnectionNotice {
  kind: "startup" | "sync" | "connection";
  phase?: ConnectionPhase;
  sandbox: boolean;
  title: string;
  description: string;
  pending: boolean;
  error: string | null;
}

export const connectionNoticeAtom = atom<ConnectionNotice | null>((get) => {
  const connection = get(connectionAtom);
  const backend = get(sandboxAtom)?.backend;
  const sandbox = Boolean(backend);
  const sync = get(sandboxSyncAtom);
  const syncing = sync.kind === "running";
  const restartRequired = sync.kind === "restart-required";
  const syncError =
    sync.kind === "failed"
      ? sync.error
      : sync.kind === "cancelled"
        ? "Sandbox sync was interrupted."
        : restartRequired
          ? sync.reason
          : null;
  if (
    sandbox &&
    (syncing || syncError !== null) &&
    connection.state === WebSocketState.OPEN
  ) {
    return {
      kind: "sync",
      sandbox,
      title: syncing
        ? "Syncing sandbox…"
        : restartRequired
          ? "Sandbox restart required"
          : "Sandbox sync failed",
      description: syncing
        ? "Applying the saved manifest to this notebook’s environment."
        : restartRequired
          ? "Restart the kernel to use the updated environment."
          : "Review the error details, then try again.",
      pending: syncing,
      error: syncError,
    };
  }
  if (connection.state === WebSocketState.CONNECTING) {
    const messages = {
      "preparing-environment": {
        title: "Preparing environment…",
        description:
          "Getting this notebook’s Python environment ready. The first start can take a few minutes.",
      },
      "starting-kernel": {
        title: "Starting kernel…",
        description:
          "The environment is prepared. Waiting for the Python kernel to connect to this notebook.",
      },
      reconnecting: {
        title: "Reconnecting…",
        description:
          "The connection was interrupted. Your notebook and existing outputs stay visible while the kernel reconnects.",
      },
    };
    return {
      kind: connection.phase === "reconnecting" ? "connection" : "startup",
      phase: connection.phase,
      sandbox,
      ...(connection.phase
        ? messages[connection.phase]
        : {
            title: "Connecting…",
            description: "Waiting for the notebook’s kernel to connect.",
          }),
      pending: true,
      error: null,
    };
  }
  if (connection.state === WebSocketState.CLOSED) {
    const startupFailed =
      connection.code === WebSocketClosedReason.KERNEL_STARTUP_ERROR;
    const environmentFailed =
      startupFailed && connection.phase === "preparing-environment";
    return {
      kind: startupFailed ? "startup" : "connection",
      phase: connection.phase,
      sandbox,
      title: environmentFailed
        ? "Sandbox setup failed"
        : startupFailed
          ? "Kernel failed to start"
          : connection.reason,
      description: environmentFailed
        ? "The notebook can’t run yet."
        : startupFailed
          ? "The Python kernel could not start. Check the error details, then try again."
          : "The connection to the notebook’s kernel was lost.",
      pending: false,
      error: startupFailed
        ? (get(kernelStartupErrorAtom) ?? connection.reason)
        : null,
    };
  }
  return null;
});
