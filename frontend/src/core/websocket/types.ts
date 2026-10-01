/* Copyright 2026 Marimo. All rights reserved. */

import type { NotificationMessageData } from "../kernel/messages";

export type ConnectionPhase =
  | NotificationMessageData<"startup-progress">["phase"]
  | "reconnecting";

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
      phase?: ConnectionPhase;
    }
  | {
      state: typeof WebSocketState.CONNECTING;
      phase?: ConnectionPhase;
    }
  | {
      state:
        | typeof WebSocketState.OPEN
        | typeof WebSocketState.CLOSING
        | typeof WebSocketState.NOT_STARTED;
    };
