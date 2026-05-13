/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { Logger } from "@/utils/Logger";
import { WebSocketClosedReason, WebSocketState } from "../types";
import { classifyCloseEvent } from "../useMarimoKernelConnection";
import { MAX_RETRIES } from "../useWebSocket";

function classify(
  reason: string | undefined,
  retryCount = 0,
  maxRetries = MAX_RETRIES,
) {
  return classifyCloseEvent({ reason }, { retryCount, maxRetries });
}

describe("classifyCloseEvent", () => {
  describe("transient closes (default branch)", () => {
    it("retries when retryCount < maxRetries", () => {
      const decision = classify(undefined, 0);
      expect(decision.kind).toBe("retry");
      expect(decision.status).toEqual({ state: WebSocketState.CONNECTING });
    });

    it("retries on each intermediate close event during a retry storm", () => {
      for (let n = 0; n < MAX_RETRIES; n++) {
        const decision = classify(undefined, n);
        expect(decision.kind).toBe("retry");
        expect(decision.status).toEqual({ state: WebSocketState.CONNECTING });
      }
    });

    it("transitions to CLOSED when retryCount reaches maxRetries", () => {
      const decision = classify(undefined, MAX_RETRIES);
      expect(decision.kind).toBe("gave-up");
      expect(decision.status).toEqual({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
        reason: "kernel not found",
      });
    });

    it("transitions to CLOSED when retryCount exceeds maxRetries", () => {
      const decision = classify(undefined, MAX_RETRIES + 5);
      expect(decision.kind).toBe("gave-up");
    });

    it("treats unknown reason strings as transient and logs a warning", () => {
      const logger = vi.spyOn(Logger, "warn").mockImplementation(() => {});
      const decision = classify("something-else", 3);
      expect(decision.kind).toBe("retry");
      expect(logger).toHaveBeenCalled();
      logger.mockRestore();
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("terminal closes (server-initiated)", () => {
    it("MARIMO_ALREADY_CONNECTED → terminal + closeTransport, with takeover", () => {
      const decision = classify("MARIMO_ALREADY_CONNECTED", 0);
      expect(decision.kind).toBe("terminal");
      expect(decision.status).toMatchObject({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.ALREADY_RUNNING,
        canTakeover: true,
      });
      if (decision.kind === "terminal") {
        expect(decision.closeTransport).toBe(true);
      }
    });

    it.each([
      "MARIMO_WRONG_KERNEL_ID",
      "MARIMO_NO_FILE_KEY",
      "MARIMO_NO_SESSION_ID",
      "MARIMO_NO_SESSION",
      "MARIMO_SHUTDOWN",
    ])("%s → terminal with KERNEL_DISCONNECTED, closes transport", (reason) => {
      const decision = classify(reason, 0);
      expect(decision.kind).toBe("terminal");
      expect(decision.status).toMatchObject({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      });
      if (decision.kind === "terminal") {
        expect(decision.closeTransport).toBe(true);
      }
    });

    it("MARIMO_MALFORMED_QUERY → terminal but does NOT close transport", () => {
      const decision = classify("MARIMO_MALFORMED_QUERY", 0);
      expect(decision.kind).toBe("terminal");
      expect(decision.status).toMatchObject({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.MALFORMED_QUERY,
      });
      if (decision.kind === "terminal") {
        expect(decision.closeTransport).toBe(false);
      }
    });

    it("MARIMO_KERNEL_STARTUP_ERROR → terminal + closeTransport", () => {
      const decision = classify("MARIMO_KERNEL_STARTUP_ERROR", 0);
      expect(decision.kind).toBe("terminal");
      expect(decision.status).toMatchObject({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
      });
      if (decision.kind === "terminal") {
        expect(decision.closeTransport).toBe(true);
      }
    });

    it("terminal closes ignore retryCount entirely", () => {
      const decision = classify("MARIMO_SHUTDOWN", 99);
      expect(decision.kind).toBe("terminal");
    });
  });

  describe("retry budget exhaustion", () => {
    it("yields retry on attempts 1..maxRetries-1 and gave-up on the final close", () => {
      const states: string[] = [];
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        states.push(classify(undefined, attempt - 1).kind);
      }
      states.push(classify(undefined, MAX_RETRIES).kind);

      expect(states).toEqual([
        ...Array.from({ length: MAX_RETRIES }, () => "retry"),
        "gave-up",
      ]);
    });
  });
});
