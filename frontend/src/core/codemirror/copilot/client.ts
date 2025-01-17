/* Copyright 2024 Marimo. All rights reserved. */
import { once } from "@/utils/once";
import { languageServerWithTransport } from "codemirror-languageserver";
import { CopilotLanguageServerClient } from "./language-server";
import { WebSocketTransport } from "@open-rpc/client-js";
import { Transport } from "@open-rpc/client-js/build/transports/Transport";
import type { JSONRPCRequestData } from "@open-rpc/client-js/build/Request";
import { waitForEnabledCopilot } from "./state";
import { waitForWs } from "@/utils/waitForWs";
import { resolveToWsUrl } from "@/core/websocket/createWsUrl";
import { Logger } from "@/utils/Logger";
import { toast } from "@/components/ui/use-toast";

// Dummy file for the copilot language server
export const COPILOT_FILENAME = "/marimo.py";
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
    await waitForWs(this.WS_URL, 3);

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
      documentUri: FILE_URI,
      languageId: LANGUAGE_ID,
      workspaceFolders: null,
      transport: createWSTransport(),
    }),
);

export function copilotServer() {
  return languageServerWithTransport({
    rootUri: FILE_URI,
    documentUri: FILE_URI,
    workspaceFolders: [],
    transport: createWSTransport(),
    client: getCopilotClient(),
    languageId: LANGUAGE_ID,
  });
}
