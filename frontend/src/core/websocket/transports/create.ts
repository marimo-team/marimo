/* Copyright 2026 Marimo. All rights reserved. */

import { createPyodideConnection } from "../../wasm/bridge";
import { isWasm } from "../../wasm/utils";
import { BasicTransport } from "./basic";
import { SseTransport } from "./sse";
import { WsTransport } from "./ws";
import type { IConnectionTransport } from "./transport";

export interface ConnectionTransportOptions {
  url: () => string;
  static: boolean;
  transportType: "websocket" | "sse";
  headers: () => Record<string, string>;
}

export function createConnectionTransport(
  options: ConnectionTransportOptions,
): IConnectionTransport {
  if (options.static) {
    return BasicTransport.empty();
  }
  if (isWasm()) {
    return createPyodideConnection();
  }
  // Read the URL lazily to follow runtime redirects.
  if (options.transportType === "sse") {
    return new SseTransport(options.url, options.headers);
  }
  return new WsTransport(options.url);
}
