/* Copyright 2026 Marimo. All rights reserved. */

export const ConnectionState = {
  NOT_STARTED: "NOT_STARTED",
  CONNECTING: "CONNECTING",
  OPEN: "OPEN",
  CLOSING: "CLOSING",
  CLOSED: "CLOSED",
} as const;

export type ConnectionState =
  (typeof ConnectionState)[keyof typeof ConnectionState];

export const ConnectionClosedReason = {
  KERNEL_DISCONNECTED: "KERNEL_DISCONNECTED",
  KERNEL_STARTUP_ERROR: "KERNEL_STARTUP_ERROR",
} as const;

export type ConnectionClosedReason =
  (typeof ConnectionClosedReason)[keyof typeof ConnectionClosedReason];

export type ConnectionStatus =
  | {
      state: typeof ConnectionState.CLOSED;
      code: ConnectionClosedReason;
      reason: string;
    }
  | {
      state: typeof ConnectionState.CONNECTING;
    }
  | {
      state:
        | typeof ConnectionState.OPEN
        | typeof ConnectionState.CLOSING
        | typeof ConnectionState.NOT_STARTED;
    };

/** The recovery policy for a closed connection. */
export interface CloseDecision {
  kind: "terminal" | "retry";
  status: ConnectionStatus;
}
