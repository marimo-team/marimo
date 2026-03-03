/* Copyright 2026 Marimo. All rights reserved. */
import { ReconnectingWebSocketTransport } from "@/core/lsp/transport";
import { waitForConnectionOpen } from "../../network/connection";
import { getRuntimeManager } from "../../runtime/config";

/**
 * Create a transport for a given LSP server.
 *
 * This ensures we are connected to the marimo runtime
 * before connecting to the LSP server.
 *
 * @param serverName - The name of the LSP server.
 * @param onReconnect - Optional callback to call after reconnection (e.g., to resync documents).
 * @returns The transport.
 */
export function createTransport(
  serverName: "pylsp" | "basedpyright" | "copilot" | "ty" | "pyrefly",
  onReconnect?: () => Promise<void>,
) {
  const runtimeManager = getRuntimeManager();
  return new ReconnectingWebSocketTransport({
    getWsUrl: () => runtimeManager.getLSPURL(serverName).toString(),
    waitForConnection: async () => {
      await waitForConnectionOpen();
    },
    onReconnect,
  });
}
