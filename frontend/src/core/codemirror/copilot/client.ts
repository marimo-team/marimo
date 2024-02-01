/* Copyright 2024 Marimo. All rights reserved. */
import { once } from "@/utils/once";
import { languageServerWithTransport } from "codemirror-languageserver";
import { CopilotLanguageServerClient } from "./language-server";
import { WebSocketTransport } from "@open-rpc/client-js";
import { Transport } from "@open-rpc/client-js/build/transports/Transport";
import { JSONRPCRequestData } from "@open-rpc/client-js/build/Request";
import { waitForEnabledCopilot } from "./state";
import { waitForWs } from "@/utils/waitForWs";

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

  constructor() {
    super();
    this.delegate = undefined;
  }

  override async connect() {
    // Wait for copilot to be enabled
    await waitForEnabledCopilot();
    // Wait for ws to be available
    await waitForWs(createWsUrl(), 3);

    // Create delegate, if it doesn't exist
    if (!this.delegate) {
      this.delegate = new WebSocketTransport(createWsUrl());
    }

    // Connect
    return this.delegate.connect();
  }

  override close() {
    this.delegate?.close();
  }

  override async sendData(
    data: JSONRPCRequestData,
    timeout?: number | null | undefined,
  ) {
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

export function createWsUrl(): string {
  // TODO: this should be configurable, but instead we add a 0 and hope it is free
  const LSP_PORT = window.location.port + 0;
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.hostname}:${LSP_PORT}/copilot`;
}
