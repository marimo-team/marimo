/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketTransport } from "@open-rpc/client-js";
import { waitForConnectionOpen } from "../../network/connection";
import { getRuntimeManager } from "../../runtime/config";

/**
 * Create a transport for a given LSP server.
 *
 * This ensures we are connected to the marimo runtime
 * before connecting to the LSP server.
 *
 * @param serverName - The name of the LSP server.
 * @returns The transport.
 */
export function createTransport(serverName: "pylsp" | "copilot" | "ty") {
  const runtimeManager = getRuntimeManager();
  const transport = new WebSocketTransport(
    runtimeManager.getLSPURL(serverName).toString(),
  );

  // Override connect to ensure runtime is healthy
  const originalConnect = transport.connect.bind(transport);
  transport.connect = async () => {
    await waitForConnectionOpen();
    return originalConnect();
  };

  return transport;
}
