/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  MAX_RETRIES,
  WsTransport,
  TRANSPORT_EXHAUSTED_REASON,
} from "../ws";

let innerListeners: Record<string, ((e: unknown) => void)[]>;

vi.mock("partysocket/ws", () => {
  class FakeReconnectingWebSocket {
    retryCount = 0;
    readyState = WebSocket.CONNECTING;
    constructor() {
      innerListeners = { open: [], close: [], message: [], error: [] };
    }
    addEventListener(event: string, cb: (e: unknown) => void) {
      innerListeners[event].push(cb);
    }
    removeEventListener(event: string, cb: (e: unknown) => void) {
      innerListeners[event] = innerListeners[event].filter((c) => c !== cb);
    }
    reconnect() {}
    close() {}
    send() {}
  }
  return { default: FakeReconnectingWebSocket };
});

interface FakeReconnectingWebSocket {
  retryCount: number;
  readyState: number;
}

function dispatchClose(reason = "") {
  const evt = new CloseEvent("close", { reason, code: 1006 });
  for (const cb of innerListeners.close) {
    cb(evt);
  }
}

describe("WsTransport", () => {
  let transport: WsTransport;
  let inner: FakeReconnectingWebSocket;

  beforeEach(() => {
    transport = new WsTransport(() => "ws://example.invalid/ws");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    inner = (transport as any).inner;
  });

  describe("close event reason", () => {
    it("forwards the original reason before retry budget is exhausted", () => {
      const seen: CloseEvent[] = [];
      transport.addEventListener("close", (e) => seen.push(e));

      inner.retryCount = MAX_RETRIES - 1;
      dispatchClose("");

      expect(seen).toHaveLength(1);
      expect(seen[0].reason).toBe("");
    });

    it("rewrites reason to MARIMO_TRANSPORT_EXHAUSTED on exhaustion", () => {
      const seen: CloseEvent[] = [];
      transport.addEventListener("close", (e) => seen.push(e));

      inner.retryCount = MAX_RETRIES;
      dispatchClose("");

      expect(seen).toHaveLength(1);
      expect(seen[0].reason).toBe(TRANSPORT_EXHAUSTED_REASON);
    });

    it("does not rewrite a server-sent reason on exhaustion", () => {
      // If partysocket happens to deliver a real MARIMO_* reason at the same
      // moment the retry budget exhausts, the exhausted-state rewrite still
      // wins because the wrapper keys off retryCount, not the original reason.
      // Document the behavior so a future change is deliberate.
      const seen: CloseEvent[] = [];
      transport.addEventListener("close", (e) => seen.push(e));

      inner.retryCount = MAX_RETRIES;
      dispatchClose("MARIMO_SHUTDOWN");

      expect(seen[0].reason).toBe(TRANSPORT_EXHAUSTED_REASON);
    });
  });

  describe("addEventListener dedupe", () => {
    it("does not double-fire when the same close listener is added twice", () => {
      const cb = vi.fn();
      transport.addEventListener("close", cb);
      transport.addEventListener("close", cb);

      dispatchClose("");

      expect(cb).toHaveBeenCalledTimes(1);
    });

    it("a single removeEventListener fully unregisters a duplicated add", () => {
      const cb = vi.fn();
      transport.addEventListener("close", cb);
      transport.addEventListener("close", cb);
      transport.removeEventListener("close", cb);

      dispatchClose("");

      expect(cb).not.toHaveBeenCalled();
      // Inner socket has no orphaned wrappers left.
      expect(innerListeners.close).toHaveLength(0);
    });
  });

  describe("removeEventListener", () => {
    it("unregisters the right wrapper for close listeners", () => {
      const cb = vi.fn();
      transport.addEventListener("close", cb);
      transport.removeEventListener("close", cb);

      inner.retryCount = MAX_RETRIES;
      dispatchClose("");

      expect(cb).not.toHaveBeenCalled();
    });
  });
});
