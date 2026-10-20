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
  kind: "terminal" | "gave-up" | "retry";
  status: ConnectionStatus;
}

export type ConnectionEvent = "open" | "close" | "message" | "error";

export interface IConnectionTransportMap {
  open: WebSocketEventMap["open"];
  message: WebSocketEventMap["message"];
  close: WebSocketEventMap["close"];
  error: WebSocketEventMap["error"];
}

export type ConnectionTransportCallback<T extends ConnectionEvent> = (
  data: IConnectionTransportMap[T],
) => void;

/** Transport readiness, using the WebSocket readyState values. */
export const TransportReadyState = {
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3,
} as const;

export type TransportReadyState =
  (typeof TransportReadyState)[keyof typeof TransportReadyState];

/** A reconnectable source of notebook messages. */
export interface NotebookTransport {
  reconnect(code?: number | undefined, reason?: string | undefined): void;
  close(): void;
  addEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void;
  removeEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void;
  readyState: TransportReadyState;
}
