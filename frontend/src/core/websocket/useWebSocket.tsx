/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";
import ReconnectingWebSocket from "partysocket/ws";
import { IReconnectingWebSocket } from "./types";
import { StaticWebsocket } from "./StaticWebsocket";

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

  const wsRef = useRef<IReconnectingWebSocket>();

  useEffect(() => {
    wsRef.current = options.static
      ? new StaticWebsocket()
      : new ReconnectingWebSocket(rest.url, undefined, {
          // We don't want Infinity retries
          maxRetries: 10,
          debug: false,
        });

    const socket = wsRef.current;
    onOpen && socket.addEventListener("open", onOpen);
    onClose && socket.addEventListener("close", onClose);
    onError && socket.addEventListener("error", onError);
    onMessage && socket.addEventListener("message", onMessage);

    return () => {
      onOpen && socket.removeEventListener("open", onOpen);
      onClose && socket.removeEventListener("close", onClose);
      onError && socket.removeEventListener("error", onError);
      onMessage && socket.removeEventListener("message", onMessage);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const socket = wsRef.current;
    return () => socket?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return wsRef;
}
