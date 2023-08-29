/* Copyright 2023 Marimo. All rights reserved. */
import { once } from "@/utils/once";
import { languageServerWithTransport } from "codemirror-languageserver";
import { CopilotLanguageServerClient } from "./language-server";
import { WebSocketTransport } from "@open-rpc/client-js";

// Dummy file for the copilot language server
export const COPILOT_FILENAME = "/marimo.py";
export const LANGUAGE_ID = "copilot";
const FILE_URI = `file://${COPILOT_FILENAME}`;

export const createWSTransport = once(
  () => new WebSocketTransport(createWsUrl())
);

export const getCopilotClient = once(
  () =>
    new CopilotLanguageServerClient({
      rootUri: null,
      documentUri: FILE_URI,
      languageId: LANGUAGE_ID,
      workspaceFolders: null,
      transport: createWSTransport(),
    })
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

function createWsUrl(): string {
  // TODO: should this be configurable or just use the port + 1?
  const LSP_PORT = Number.parseInt(window.location.port) + 1;
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.hostname}:${LSP_PORT}/copilot`;
}
