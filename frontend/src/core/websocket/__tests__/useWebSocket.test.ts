/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { BasicTransport } from "../transports/basic";
import { SseTransport } from "../transports/sse";
import { WsTransport } from "../transports/ws";
import { createConnectionTransport } from "../useWebSocket";

vi.mock("../../wasm/utils", () => ({
  isWasm: () => false,
}));

describe("createConnectionTransport", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  const options = {
    url: () => "http://localhost/ws",
    headers: () => ({}),
  };

  it("uses BasicTransport for static notebooks", () => {
    const transport = createConnectionTransport({
      ...options,
      static: true,
      transportType: "websocket",
    });
    expect(transport).toBeInstanceOf(BasicTransport);
  });

  it("uses WsTransport by default", () => {
    const transport = createConnectionTransport({
      ...options,
      static: false,
      transportType: "websocket",
    });
    expect(transport).toBeInstanceOf(WsTransport);
  });

  it("uses SseTransport when the transport type is sse", () => {
    const transport = createConnectionTransport({
      ...options,
      static: false,
      transportType: "sse",
    });
    expect(transport).toBeInstanceOf(SseTransport);
  });
});
