/* Copyright 2026 Marimo. All rights reserved. */

// TODO: rename to ConnectionState
export const WebSocketState = {
  NOT_STARTED: "NOT_STARTED",
  CONNECTING: "CONNECTING",
  OPEN: "OPEN",
  CLOSING: "CLOSING",
  CLOSED: "CLOSED",
} as const;

export type WebSocketState =
  (typeof WebSocketState)[keyof typeof WebSocketState];

export const WebSocketClosedReason = {
  KERNEL_DISCONNECTED: "KERNEL_DISCONNECTED",
  ALREADY_RUNNING: "ALREADY_RUNNING",
  MALFORMED_QUERY: "MALFORMED_QUERY",
  KERNEL_STARTUP_ERROR: "KERNEL_STARTUP_ERROR",
} as const;

export type WebSocketClosedReason =
  (typeof WebSocketClosedReason)[keyof typeof WebSocketClosedReason];

export type ConnectionStatus =
  | {
      state: typeof WebSocketState.CLOSED;
      code: WebSocketClosedReason;
      /**
       * Human-readable reason for closing the connection.
       */
      reason: string;
      /**
       * Whether the current session can be taken over by another session,
       * since we only allow single-user editing.
       */
      canTakeover?: boolean;
    }
  | {
      state:
        | typeof WebSocketState.CONNECTING
        | typeof WebSocketState.OPEN
        | typeof WebSocketState.CLOSING
        | typeof WebSocketState.NOT_STARTED;
    };
