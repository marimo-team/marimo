/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useState } from "react";
import { Logger } from "@/utils/Logger";
import { createPyodideConnection } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import { BasicTransport } from "./transports/basic";
import { SseTransport } from "./transports/sse";
import { WsTransport } from "./transports/ws";
import type { IConnectionTransport } from "./transports/transport";

interface UseConnectionTransportOptions {
  url: () => string;
  static: boolean;
  transportType: "websocket" | "sse";
  /** Request headers for the SSE transport (auth); unused by WebSockets. */
  headers: () => Record<string, string>;
  waitToConnect: () => Promise<void>;
  onOpen: (event: WebSocketEventMap["open"]) => void;
  onMessage: (event: WebSocketEventMap["message"]) => void;
  onClose: (event: WebSocketEventMap["close"]) => void;
  onError: (event: WebSocketEventMap["error"]) => void;
}

export function createConnectionTransport(
  options: Pick<
    UseConnectionTransportOptions,
    "url" | "static" | "transportType" | "headers"
  >,
): IConnectionTransport {
  if (options.static) {
    return BasicTransport.empty();
  }
  if (isWasm()) {
    return createPyodideConnection();
  }
  // urlProvider is passed lazily; it may change after a runtime redirect.
  if (options.transportType === "sse") {
    return new SseTransport(options.url, options.headers);
  }
  return new WsTransport(options.url);
}

/**
 * A hook for creating a connection transport with React.
 */
export function useConnectionTransport(options: UseConnectionTransportOptions) {
  const { onOpen, onMessage, onClose, onError, waitToConnect } = options;

  // oxlint-disable-next-line react/hook-use-state
  const [transport] = useState<IConnectionTransport>(() => {
    const socket = createConnectionTransport(options);

    socket.addEventListener("open", onOpen);
    socket.addEventListener("close", onClose);
    socket.addEventListener("error", onError);
    socket.addEventListener("message", onMessage);

    return socket;
  });

  useEffect(() => {
    // If it's closed, reconnect
    // This starts closed, so we need to connect for the first time
    if (transport.readyState === WebSocket.CLOSED) {
      void waitToConnect()
        .then(() => transport.reconnect())
        .catch((error) => {
          Logger.error("Healthy connection never made", error);
          transport.close();
        });
    }

    return () => {
      Logger.warn(
        "useConnectionTransport is unmounting. This likely means there is a bug.",
      );
      transport.close();
      transport.removeEventListener("open", onOpen);
      transport.removeEventListener("close", onClose);
      transport.removeEventListener("error", onError);
      transport.removeEventListener("message", onMessage);
    };
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [transport]);

  return transport;
}
