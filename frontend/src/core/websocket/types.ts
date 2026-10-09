/* Copyright 2026 Marimo. All rights reserved. */

import type { NotificationMessageData } from "../kernel/messages";

export type ConnectionPhase =
  | NotificationMessageData<"startup-progress">["phase"]
  | "reconnecting";

export const ConnectionState = {
  NOT_STARTED: "NOT_STARTED",
  CONNECTING: "CONNECTING",
  OPEN: "OPEN",
  CLOSING: "CLOSING",
  CLOSED: "CLOSED",
} as const;

export type ConnectionState =
  (typeof ConnectionState)[keyof typeof ConnectionState];

export const WebSocketClosedReason = {
  KERNEL_DISCONNECTED: "KERNEL_DISCONNECTED",
  KERNEL_STARTUP_ERROR: "KERNEL_STARTUP_ERROR",
} as const;

export type WebSocketClosedReason =
  (typeof WebSocketClosedReason)[keyof typeof WebSocketClosedReason];

export type ConnectionStatus =
  | {
      state: typeof ConnectionState.CLOSED;
      code: WebSocketClosedReason;
      /**
       * Human-readable reason for closing the connection.
       */
      reason: string;
      phase?: ConnectionPhase;
    }
  | {
      state: typeof ConnectionState.CONNECTING;
      phase?: ConnectionPhase;
    }
  | {
      state:
        | typeof ConnectionState.OPEN
        | typeof ConnectionState.CLOSING
        | typeof ConnectionState.NOT_STARTED;
    };
