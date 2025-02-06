/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketClientTransport } from "@modelcontextprotocol/sdk/client/websocket.js";
import { mcpExtension as mcpExtensionInternal } from "@marimo-team/codemirror-mcp";
import { resolveToWsUrl } from "@/core/websocket/createWsUrl";
import { Logger } from "@/utils/Logger";
import type { Extension } from "@codemirror/state";

export function mcpExtension(): Extension {
  return mcpExtensionInternal({
    // Required options
    transport: new WebSocketClientTransport(
      new URL(resolveToWsUrl("/api/mcp/ws/local")),
    ),

    // Optional options
    logger: console,
    clientOptions: {
      name: "marimo-editor",
      version: "1.0.0",
    },
    onResourceClick: (resource) => {
      Logger.log("onResourceClick", resource);
      // Open resource
      // e.g. open in a tab, etc.
    },
  });
}
