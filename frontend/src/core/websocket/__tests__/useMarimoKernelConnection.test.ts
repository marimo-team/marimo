/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { Logger } from "@/utils/Logger";
import { WebSocketClosedReason, WebSocketState } from "../types";
import { classifyCloseEvent } from "../useMarimoKernelConnection";

function classify(reason: string | undefined) {
  return classifyCloseEvent({ reason });
}

describe("classifyCloseEvent", () => {
  describe("transient closes (default branch)", () => {
    it("retries on empty/undefined reason", () => {
      const decision = classify(undefined);
      expect(decision.kind).toBe("retry");
      expect(decision.status).toEqual({ state: WebSocketState.CONNECTING });
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
    ])("%s → terminal with KERNEL_DISCONNECTED, closes transport", (reason) => {
      const decision = classify(reason);
      expect(decision.kind).toBe("terminal");
      expect(decision.status).toMatchObject({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      });
      if (decision.kind === "terminal") {
        expect(decision.closeTransport).toBe(true);
      }
    });

    it("MARIMO_KERNEL_STARTUP_ERROR → terminal + closeTransport", () => {
      const decision = classify("MARIMO_KERNEL_STARTUP_ERROR");
      expect(decision.kind).toBe("terminal");
      expect(decision.status).toMatchObject({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
      });
      if (decision.kind === "terminal") {
        expect(decision.closeTransport).toBe(true);
      }
    });
  });

  describe("transport exhaustion", () => {
    it("MARIMO_TRANSPORT_EXHAUSTED → gave-up with KERNEL_DISCONNECTED", () => {
      const decision = classify("MARIMO_TRANSPORT_EXHAUSTED");
      expect(decision.kind).toBe("gave-up");
      expect(decision.status).toEqual({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
        reason: "kernel not found",
      });
    });
  });
});
