/* Copyright 2024 Marimo. All rights reserved. */
import { once } from "@/utils/once";
import { languageServerWithClient } from "@marimo-team/codemirror-languageserver";
import { CopilotLanguageServerClient } from "./language-server";
import { WebSocketTransport } from "@open-rpc/client-js";
import { Transport } from "@open-rpc/client-js/build/transports/Transport";
import type { JSONRPCRequestData } from "@open-rpc/client-js/build/Request";
import { waitForEnabledCopilot } from "./state";
import { Logger } from "@/utils/Logger";
import { toast } from "@/components/ui/use-toast";
import { resolveToWsUrl } from "@/core/websocket/createWsUrl";
import { waitForConnectionOpen } from "@/core/network/connection";

// Dummy file for the copilot language server
export const COPILOT_FILENAME = "/__marimo_copilot__.py";
export const LANGUAGE_ID = "copilot";
const FILE_URI = `file://${COPILOT_FILENAME}`;

export const createWSTransport = once(() => {
  return new LazyWebsocketTransport();
});

/**
 * Custom WSTransport that:
 *  - waits for copilot to be enabled
 *  - wait for the websocket to be available
 */
class LazyWebsocketTransport extends Transport {
  private delegate: WebSocketTransport | undefined;
  private readonly WS_URL = resolveToWsUrl("lsp/copilot");

  constructor() {
    super();
    this.delegate = undefined;
  }

  private async tryConnect(retries = 3, delayMs = 1000): Promise<void> {
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        // Create delegate, if it doesn't exist
        if (!this.delegate) {
          this.delegate = new WebSocketTransport(this.WS_URL);
        }
        await this.delegate.connect();
        Logger.log("Copilot#connect: Connected successfully");
        return;
      } catch (error) {
        Logger.warn(
          `Copilot#connect: Connection attempt ${attempt}/${retries} failed`,
          error,
        );
        if (attempt === retries) {
          this.delegate = undefined;
          // Show error toast on final retry
          toast({
            variant: "danger",
            title: "GitHub Copilot Connection Error",
            description:
              "Failed to connect to GitHub Copilot. Please check settings and try again.",
          });
          throw error;
        }
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }

  override async connect() {
    // Wait for copilot to be enabled
    await waitForEnabledCopilot();
    // Wait for ws to be available with retries
    await waitForConnectionOpen();

    // Try connecting with retries
    return this.tryConnect();
  }

  override close() {
    this.delegate?.close();
    this.delegate = undefined;
  }

  override async sendData(
    data: JSONRPCRequestData,
    timeout: number | null | undefined,
  ) {
    // Clamp timeout to 5 seconds
    timeout = Math.min(timeout ?? 5000, 5000);
    return this.delegate?.sendData(data, timeout);
  }
}

export const getCopilotClient = once(
  () =>
    new CopilotLanguageServerClient({
      rootUri: FILE_URI,
      workspaceFolders: null,
      transport: createWSTransport(),
    }),
);

export function copilotServer() {
  return languageServerWithClient({
    documentUri: FILE_URI,
    client: getCopilotClient(),
    languageId: LANGUAGE_ID,
    // Disable all basic LSP features
    // we only need textDocument/didChange
    hoverEnabled: false,
    completionEnabled: false,
    definitionEnabled: false,
    renameEnabled: false,
    codeActionsEnabled: false,
    signatureHelpEnabled: false,
    diagnosticsEnabled: false,
    sendIncrementalChanges: false,
  });
}
