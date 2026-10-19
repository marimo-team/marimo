/* Copyright 2026 Marimo. All rights reserved. */

import type { CloseDecision } from "../host/connection";
import { logNever } from "@/utils/assertNever";
import { TRANSPORT_EXHAUSTED_REASON } from "./transports/ws";
import { ConnectionState, WebSocketClosedReason } from "./types";

// Keep server reasons in sync with ws_endpoint.py and ws/*.py.
// SSE carries the same reasons in close events. Unclassified reasons retry.
type CloseReason =
  | "MARIMO_NO_FILE_KEY"
  | "MARIMO_NO_SESSION_ID"
  | "MARIMO_NO_SESSION"
  | "MARIMO_SHUTDOWN"
  | "MARIMO_KERNEL_STARTUP_ERROR"
  | "MARIMO_UNAUTHORIZED"
  | "MARIMO_KIOSK_NOT_ALLOWED"
  | typeof TRANSPORT_EXHAUSTED_REASON;

export function classifyCloseEvent(event: { reason?: string }): CloseDecision {
  switch (event.reason as CloseReason | undefined) {
    case TRANSPORT_EXHAUSTED_REASON:
      return {
        kind: "gave-up",
        status: {
          state: ConnectionState.CLOSED,
          code: WebSocketClosedReason.KERNEL_DISCONNECTED,
          reason: "kernel not found",
        },
      };
    case "MARIMO_NO_FILE_KEY":
    case "MARIMO_NO_SESSION_ID":
    case "MARIMO_NO_SESSION":
    case "MARIMO_SHUTDOWN":
      return {
        kind: "terminal",
        status: {
          state: ConnectionState.CLOSED,
          code: WebSocketClosedReason.KERNEL_DISCONNECTED,
          reason: "kernel not found",
        },
      };
    case "MARIMO_UNAUTHORIZED":
      return {
        kind: "terminal",
        status: {
          state: ConnectionState.CLOSED,
          code: WebSocketClosedReason.KERNEL_DISCONNECTED,
          reason: "not authorized",
        },
      };
    case "MARIMO_KIOSK_NOT_ALLOWED":
      return {
        kind: "terminal",
        status: {
          state: ConnectionState.CLOSED,
          code: WebSocketClosedReason.KERNEL_DISCONNECTED,
          reason: "kiosk mode is not available for this session",
        },
      };
    case "MARIMO_KERNEL_STARTUP_ERROR":
      return {
        kind: "terminal",
        status: {
          state: ConnectionState.CLOSED,
          code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
          reason: "Failed to start kernel sandbox",
        },
      };
    default:
      if (event.reason) {
        logNever(event.reason as never);
      }
  }

  return {
    kind: "retry",
    status: { state: ConnectionState.CONNECTING },
  };
}
