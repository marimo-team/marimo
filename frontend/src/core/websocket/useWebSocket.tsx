/* Copyright 2026 Marimo. All rights reserved. */

import ReconnectingWebSocket from "partysocket/ws";
import { useEffect, useState } from "react";
import { Logger } from "@/utils/Logger";
import { createPyodideConnection } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import { BasicTransport } from "./transports/basic";
import type { IConnectionTransport } from "./transports/transport";

interface UseConnectionTransportOptions {
  url: () => string;
  static: boolean;
  waitToConnect: () => Promise<void>;
  onOpen: (event: WebSocketEventMap["open"]) => void;
  onMessage: (event: WebSocketEventMap["message"]) => void;
  onClose: (event: WebSocketEventMap["close"]) => void;
  onError: (event: WebSocketEventMap["error"]) => void;
}

function createConnectionTransport(
  options: Pick<UseConnectionTransportOptions, "url" | "static">,
): IConnectionTransport {
  if (options.static) {
    return BasicTransport.empty();
  }
  if (isWasm()) {
    return createPyodideConnection();
  }
  // Create a connection transport using the ReconnectingWebSocket from partysocket
  // This handles reconnecting when the connection is lost.
  const urlProvider = options.url; // We don't call the URL provider now since it may change (i.e. if the runtime redirects)
  return new ReconnectingWebSocket(urlProvider, undefined, {
    // We don't want Infinity retries
    maxRetries: 10,
    debug: false,
    startClosed: true,
    // long timeout -- the server can become slow when many notebooks
    // are open.
    connectionTimeout: 10_000,
  });
}

/**
 * A hook for creating a connection transport with React.
 */
export function useConnectionTransport(options: UseConnectionTransportOptions) {
  const { onOpen, onMessage, onClose, onError, waitToConnect } = options;

  // eslint-disable-next-line react/hook-use-state
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transport]);

  return transport;
}
