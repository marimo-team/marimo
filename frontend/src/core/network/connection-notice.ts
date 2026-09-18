/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { sandboxAtom, sandboxSyncAtom } from "@/core/packages/sandbox-state";
import { WebSocketClosedReason, WebSocketState } from "@/core/websocket/types";
import { connectionAtom } from "./connection";

export const connectionNoticeAtom = atom((get) => {
  const connection = get(connectionAtom);
  const backend = get(sandboxAtom)?.backend;
  const sandbox = Boolean(backend);
  const sync = get(sandboxSyncAtom);
  if (
    sandbox &&
    (sync.pending || sync.error) &&
    connection.state === WebSocketState.OPEN
  ) {
    return {
      sandbox,
      title: sync.pending ? "Syncing sandbox…" : "Sandbox sync failed",
      description: sync.pending
        ? "Applying the saved manifest to this notebook’s environment."
        : "Review the error details, then try again.",
      pending: sync.pending,
      error: sync.error,
    };
  }
  if (connection.state === WebSocketState.CONNECTING) {
    const messages = {
      "preparing-environment": {
        title: backend
          ? `Preparing ${backend} sandbox…`
          : "Preparing environment…",
        description:
          "Getting this notebook’s Python environment ready. The first start can take a few minutes.",
      },
      "starting-kernel": {
        title: "Starting notebook…",
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
