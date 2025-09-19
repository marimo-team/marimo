/* Copyright 2024 Marimo. All rights reserved. */

import type ReconnectingWebSocket from "partysocket/ws";

export const WebSocketState = {
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
        | typeof WebSocketState.CLOSING;
    };

type PublicInterface<T> = {
  [P in keyof T]: T[P];
};

export type IReconnectingWebSocket = PublicInterface<ReconnectingWebSocket>;
