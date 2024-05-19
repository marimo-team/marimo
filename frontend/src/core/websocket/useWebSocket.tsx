/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useState } from "react";
import ReconnectingWebSocket from "partysocket/ws";
import { IReconnectingWebSocket } from "./types";
import { StaticWebsocket } from "./StaticWebsocket";
import { isPyodide } from "../pyodide/utils";
import { PyodideBridge, PyodideWebsocket } from "../pyodide/bridge";

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

  // eslint-disable-next-line react/hook-use-state
  const [ws] = useState<IReconnectingWebSocket>(() => {
    const socket: IReconnectingWebSocket = isPyodide()
      ? new PyodideWebsocket(PyodideBridge.INSTANCE)
      : options.static
        ? new StaticWebsocket()
        : new ReconnectingWebSocket(rest.url, undefined, {
            // We don't want Infinity retries
            maxRetries: 10,
            debug: false,
          });

    onOpen && socket.addEventListener("open", onOpen);
    onClose && socket.addEventListener("close", onClose);
    onError && socket.addEventListener("error", onError);
    onMessage && socket.addEventListener("message", onMessage);

    return socket;
  });

  useEffect(() => {
    return () => {
      onOpen && ws.removeEventListener("open", onOpen);
      onClose && ws.removeEventListener("close", onClose);
      onError && ws.removeEventListener("error", onError);
      onMessage && ws.removeEventListener("message", onMessage);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return ws;
}
