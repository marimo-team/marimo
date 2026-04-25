/* Copyright 2026 Marimo. All rights reserved. */

import {
  type ConnectionStatus,
  WebSocketClosedReason,
  WebSocketState,
} from "./types";

/**
 * Result of classifying a WebSocket close event.
 *
 * - `terminal`: server-initiated close that cannot recover via retry.
 *   `closeTransport` controls whether to call `ws.close()`.
 * - `gave-up`: the transport has exhausted its retry budget.
 * - `retry`: transient close; the consumer should reconnect.
 */
export type CloseDecision =
  | { kind: "terminal"; status: ConnectionStatus; closeTransport: boolean }
  | { kind: "gave-up"; status: ConnectionStatus }
  | { kind: "retry"; status: ConnectionStatus };

export interface CloseEventLike {
  code?: number;
  reason?: string;
}

export function classifyCloseEvent(
  event: CloseEventLike,
  context: { retryCount: number; maxRetries: number },
): CloseDecision {
  switch (event.reason) {
    case "MARIMO_ALREADY_CONNECTED":
      return {
        kind: "terminal",
        status: {
          state: WebSocketState.CLOSED,
          code: WebSocketClosedReason.ALREADY_RUNNING,
          reason: "another browser tab is already connected to the kernel",
          canTakeover: true,
        },
        closeTransport: true,
      };

    case "MARIMO_WRONG_KERNEL_ID":
    case "MARIMO_NO_FILE_KEY":
    case "MARIMO_NO_SESSION_ID":
    case "MARIMO_NO_SESSION":
    case "MARIMO_SHUTDOWN":
      return {
        kind: "terminal",
        status: {
          state: WebSocketState.CLOSED,
          code: WebSocketClosedReason.KERNEL_DISCONNECTED,
          reason: "kernel not found",
        },
        closeTransport: true,
      };

    case "MARIMO_MALFORMED_QUERY":
      return {
        kind: "terminal",
        status: {
          state: WebSocketState.CLOSED,
          code: WebSocketClosedReason.MALFORMED_QUERY,
          reason:
            "the kernel did not recognize a request; please file a bug with marimo",
        },
        closeTransport: false,
      };

    case "MARIMO_KERNEL_STARTUP_ERROR":
      return {
        kind: "terminal",
        status: {
          state: WebSocketState.CLOSED,
          code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
          reason: "Failed to start kernel sandbox",
        },
        closeTransport: true,
      };

    default:
      // partysocket stops retrying silently once `maxRetries` is hit; surface
      // CLOSED so callers can detect the give-up.
      if (context.retryCount >= context.maxRetries) {
        return {
          kind: "gave-up",
          status: {
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.KERNEL_DISCONNECTED,
            reason: "kernel not found",
          },
        };
      }
      return {
        kind: "retry",
        status: { state: WebSocketState.CONNECTING },
      };
  }
}
