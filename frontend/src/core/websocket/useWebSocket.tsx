/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useState } from "react";
import ReconnectingWebSocket from "partysocket/ws";
import type { IReconnectingWebSocket } from "./types";
import { StaticWebsocket } from "./StaticWebsocket";
import { isWasm } from "../wasm/utils";
import { PyodideBridge, PyodideWebsocket } from "../wasm/bridge";
import { Logger } from "@/utils/Logger";

interface UseWebSocketOptions {
  url: string;
  static: boolean;
  onOpen?: (event: WebSocketEventMap["open"]) => void;
  onMessage?: (event: WebSocketEventMap["message"]) => void;
  onClose?: (event: WebSocketEventMap["close"]) => void;
  onError?: (event: WebSocketEventMap["error"]) => void;
}

/**
 * A hook for creating a WebSocket connection with React.
 *
 * We use the WebSocket from partysocket, which is a wrapper around the native WebSocket API with reconnect logic.
 */
export function useWebSocket(options: UseWebSocketOptions) {
  const { onOpen, onMessage, onClose, onError, ...rest } = options;

  const [ws] = useState<IReconnectingWebSocket>(() => {
    const socket: IReconnectingWebSocket = isWasm()
      ? new PyodideWebsocket(PyodideBridge.INSTANCE)
      : options.static
        ? new StaticWebsocket()
        : new ReconnectingWebSocket(rest.url, undefined, {
            // We don't want Infinity retries
            maxRetries: 10,
            debug: false,
            startClosed: true,
            // long timeout -- the server can become slow when many notebooks
            // are open.
            connectionTimeout: 10_000,
          });

    if (onOpen) {
      socket.addEventListener("open", onOpen);
    }
    if (onClose) {
      socket.addEventListener("close", onClose);
    }
    if (onError) {
      socket.addEventListener("error", onError);
    }
    if (onMessage) {
      socket.addEventListener("message", onMessage);
    }

    return socket;
  });

  useEffect(() => {
    // If it's closed, reconnect
    // This starts closed, so we need to connect for the first time
    if (ws.readyState === WebSocket.CLOSED) {
      ws.reconnect();
    }

    return () => {
      Logger.warn(
        "useWebSocket is unmounting. This likely means there is a bug.",
      );
      ws.close();
      if (onOpen) {
        ws.removeEventListener("open", onOpen);
      }
      if (onClose) {
        ws.removeEventListener("close", onClose);
      }
      if (onError) {
        ws.removeEventListener("error", onError);
      }
      if (onMessage) {
        ws.removeEventListener("message", onMessage);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws]);

  return ws;
}
