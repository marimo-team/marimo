/* Copyright 2026 Marimo. All rights reserved. */

import { languageServerWithClient } from "@marimo-team/codemirror-languageserver";
import { toast } from "@/components/ui/use-toast";
import { resolvedMarimoConfigAtom } from "@/core/config/config";
import { waitForConnectionOpen } from "@/core/network/connection";
import { getRuntimeManager } from "@/core/runtime/config";
import { store } from "@/core/state/jotai";
import { once } from "@/utils/once";
import { CopilotLanguageServerClient } from "./language-server";
import { waitForEnabledCopilot } from "./state";
import { LazyWebsocketTransport } from "./transport";

// Dummy file for the copilot language server
export const COPILOT_FILENAME = "/__marimo_copilot__.py";
export const LANGUAGE_ID = "copilot";
const FILE_URI = `file://${COPILOT_FILENAME}`;

export const createWSTransport = once(() => {
  const runtimeManager = getRuntimeManager();
  return new LazyWebsocketTransport({
    getWsUrl: () => runtimeManager.getLSPURL("copilot").toString(),
    waitForReady: async () => {
      await waitForEnabledCopilot();
      await waitForConnectionOpen();
    },
    showError: (title, description) => {
      toast({
        variant: "danger",
        title,
        description,
      });
    },
  });
});

export const getCopilotClient = once(() => {
  const userConfig = store.get(resolvedMarimoConfigAtom);
  const copilotSettings = userConfig.ai?.github?.copilot_settings ?? {};

  return new CopilotLanguageServerClient({
    rootUri: FILE_URI,
    workspaceFolders: null,
    transport: createWSTransport(),
    copilotSettings,
  });
});

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
