/* Copyright 2024 Marimo. All rights reserved. */
import { mcpExtension as mcpExtensionInternal } from "@marimo-team/codemirror-mcp";
import { resolveToWsUrl } from "@/core/websocket/createWsUrl";
import { Logger } from "@/utils/Logger";
import type { Extension } from "@codemirror/state";
import { getSessionId } from "@/core/kernel/session";
import {
  type JSONRPCMessage,
  type Resource,
  JSONRPCMessageSchema,
} from "@modelcontextprotocol/sdk/types";

export function mcpExtension(): Extension {
  const wsUrl = resolveToWsUrl(`/mcp/ws?session_id=${getSessionId()}`);
  const transport = new WebSocketClientTransport(new URL(wsUrl));
  return mcpExtensionInternal({
    // Required options
    transport: transport,

    // Optional options
    logger: console,
    clientOptions: {
      name: "marimo-editor",
      version: "1.0.0",
    },
    onResourceClick: (resource: Resource) => {
      Logger.log("onResourceClick", resource);
      // TODO(mcp): Open resource, e.g. open in a tab, etc.
    },
  });
}

export class WebSocketClientTransport {
  private _socket?: WebSocket;
  private _url: URL;

  onclose?: () => void;
  onerror?: (error: Error) => void;
  onmessage?: (message: JSONRPCMessage) => void;

  constructor(url: URL) {
    this._url = url;
  }

  start(): Promise<void> {
    if (this._socket) {
      throw new Error(
        "WebSocketClientTransport already started! If using Client class, note that connect() calls start() automatically.",
      );
    }

    return new Promise((resolve, reject) => {
      this._socket = new WebSocket(this._url);

      this._socket.onerror = (event) => {
        const error = event instanceof Error
          ? event
          : "error" in event && event.error instanceof Error
            ? event.error
            : new Error(`WebSocket error: ${JSON.stringify(event)}`);
        reject(error);
        this.onerror?.call(this, error);
      };

      this._socket.onopen = () => {
        resolve();
      };

      this._socket.onclose = () => {
        this.onclose?.call(this);
      };

      this._socket.onmessage = (event) => {
        let message;
        try {
          message = JSONRPCMessageSchema.parse(JSON.parse(event.data));
        } catch (error) {
          const typedError = error instanceof Error ? error : new Error(String(error));
          this.onerror?.call(this, typedError);
          return;
        }
        this.onmessage?.call(this, message);
      };
    });
  }

  async close(): Promise<void> {
    this._socket?.close();
  }

  send(message: JSONRPCMessage): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this._socket) {
        reject(new Error("Not connected"));
        return;
      }
      this._socket?.send(JSON.stringify(message));
      resolve();
    });
  }
}
