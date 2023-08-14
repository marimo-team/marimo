/* Copyright 2023 Marimo. All rights reserved. */

export enum WebSocketState {
  CONNECTING = 0,
  OPEN = 1,
  CLOSING = 2,
  CLOSED = 3,
}

export enum WebSocketClosedReason {
  KERNEL_DISCONNECTED = "KERNEL_DISCONNECTED",
  ALREADY_RUNNING = "ALREADY_RUNNING",
  MALFORMED_QUERY = "MALFORMED_QUERY",
}

export type ConnectionStatus =
  | {
      state: WebSocketState.CLOSED;
      code: WebSocketClosedReason;
      /**
       * Human-readable reason for closing the connection.
       */
      reason: string;
    }
  | {
      state:
        | WebSocketState.CONNECTING
        | WebSocketState.OPEN
        | WebSocketState.CLOSING;
    };
