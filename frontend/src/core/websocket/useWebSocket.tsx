/* Copyright 2024 Marimo. All rights reserved. */

import ReconnectingWebSocket from "partysocket/ws";
import { useEffect, useState } from "react";
import { Logger } from "@/utils/Logger";
import { isStaticNotebook } from "../static/static-state";
import { PyodideBridge, PyodideWebsocket } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import { StaticWebsocket } from "./StaticWebsocket";
import type { IReconnectingWebSocket } from "./types";

interface UseWebSocketOptions {
  url: () => string;
  static: boolean;
  waitToConnect?: () => Promise<void>;
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
  const { onOpen, onMessage, onClose, onError, waitToConnect, ...rest } =
    options;

  // eslint-disable-next-line react/hook-use-state
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

    onOpen && socket.addEventListener("open", onOpen);
    onClose && socket.addEventListener("close", onClose);
    onError && socket.addEventListener("error", onError);
    onMessage && socket.addEventListener("message", onMessage);

    return socket;
  });

  useEffect(() => {
    // If it's closed, reconnect
    // This starts closed, so we need to connect for the first time
    if (ws.readyState === WebSocket.CLOSED) {
      // Ignore waitToConnect for static and wasm notebooks
      if (waitToConnect && !isStaticNotebook() && !isWasm()) {
        waitToConnect()
          .then(() => {
            ws.reconnect();
          })
          .catch((error) => {
            Logger.error("Healthy connection never made", error);
            ws.close();
          });
      } else {
        ws.reconnect();
      }
    }

    return () => {
      Logger.warn(
        "useWebSocket is unmounting. This likely means there is a bug.",
      );
      ws.close();
      onOpen && ws.removeEventListener("open", onOpen);
      onClose && ws.removeEventListener("close", onClose);
      onError && ws.removeEventListener("error", onError);
      onMessage && ws.removeEventListener("message", onMessage);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws]);

  return ws;
}
