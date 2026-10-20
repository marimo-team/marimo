/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { Logger } from "@/utils/Logger";
import { WebSocketClosedReason, ConnectionState } from "../types";
import { classifyCloseEvent } from "../connection-state";

function classify(reason: string | undefined) {
  return classifyCloseEvent({ reason });
}

describe("classifyCloseEvent", () => {
  describe("transient closes (default branch)", () => {
    it("retries on empty/undefined reason", () => {
      const decision = classify(undefined);
      expect(decision).toEqual({
        kind: "retry",
        status: { state: ConnectionState.CONNECTING },
      });
    });

    it("treats unknown reason strings as transient and logs a warning", () => {
      const logger = vi.spyOn(Logger, "warn").mockImplementation(() => {});
      const decision = classify("something-else");
      expect(decision.kind).toBe("retry");
      expect(logger).toHaveBeenCalled();
      logger.mockRestore();
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("terminal closes (server-initiated)", () => {
    it.each([
      "MARIMO_NO_FILE_KEY",
      "MARIMO_NO_SESSION_ID",
      "MARIMO_NO_SESSION",
      "MARIMO_SHUTDOWN",
      // Delivered as in-band close events by the SSE transport; must be
      // terminal or a rejected client would reconnect forever.
      "MARIMO_UNAUTHORIZED",
      "MARIMO_KIOSK_NOT_ALLOWED",
    ])("%s → terminal with KERNEL_DISCONNECTED", (reason) => {
      const decision = classify(reason);
      expect(decision).toMatchObject({
        kind: "terminal",
        status: {
          state: ConnectionState.CLOSED,
          code: WebSocketClosedReason.KERNEL_DISCONNECTED,
        },
      });
    });

    it("MARIMO_KERNEL_STARTUP_ERROR → terminal", () => {
      const decision = classify("MARIMO_KERNEL_STARTUP_ERROR");
      expect(decision).toMatchObject({
        kind: "terminal",
        status: {
          state: ConnectionState.CLOSED,
          code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
        },
      });
    });
  });

  describe("transport exhaustion", () => {
    it("MARIMO_TRANSPORT_EXHAUSTED → gave-up with KERNEL_DISCONNECTED", () => {
      const decision = classify("MARIMO_TRANSPORT_EXHAUSTED");
      expect(decision.kind).toBe("gave-up");
      expect(decision.status).toEqual({
        state: ConnectionState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
        reason: "kernel not found",
      });
    });
  });
});
