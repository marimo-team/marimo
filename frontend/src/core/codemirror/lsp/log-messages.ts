/* Copyright 2026 Marimo. All rights reserved. */

import type { JSONRPCMessage } from "@marimo-team/codemirror-languageserver";
import { addLogs } from "@/core/cells/cells";
import { isRecord } from "@/utils/records";

// LSP MessageType: 1 = Error, 2 = Warning, 3 = Info, 4 = Log, 5 = Debug
const ERROR_MESSAGE_TYPES = new Set<unknown>([1, 2]);

/**
 * Forward a server's `window/logMessage` notifications to the Logs panel.
 * Servers report failures they can't surface as diagnostics this way, such as
 * a missing interpreter or a plugin that failed to load.
 */
export function handleLogMessage(
  serverName: string,
  message: JSONRPCMessage,
): void {
  if (!("method" in message) || message.method !== "window/logMessage") {
    return;
  }
  const params: unknown = message.params;
  if (!isRecord(params) || typeof params.message !== "string") {
    return;
  }

  addLogs({
    logs: [
      {
        timestamp: Date.now() / 1000,
        level: ERROR_MESSAGE_TYPES.has(params.type) ? "stderr" : "stdout",
        message: params.message,
        source: { type: "lsp", name: serverName },
      },
    ],
  });
}
