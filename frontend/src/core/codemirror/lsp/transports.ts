/* Copyright 2026 Marimo. All rights reserved. */
import { ReconnectingWebSocketTransport } from "@/core/lsp/transport";
import { waitForConnectionOpen } from "../../network/connection";
import { getRuntimeManager } from "../../runtime/config";
import { handleLogMessage } from "./log-messages";

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
  const transport = new ReconnectingWebSocketTransport({
    getWsUrl: () => runtimeManager.getLSPURL(serverName).toString(),
    waitForConnection: async () => {
      await waitForConnectionOpen();
    },
    onReconnect,
  });

  // Handled on the transport, not the client, so that logs are captured before
  // the client initializes — which is when startup failures are reported.
  transport.onMessage((message) => handleLogMessage(serverName, message));

  return transport;
}
