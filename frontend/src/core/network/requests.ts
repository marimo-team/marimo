/* Copyright 2024 Marimo. All rights reserved. */
import { IslandsPyodideBridge } from "../islands/bridge";
import { isIslands } from "../islands/utils";
import { PyodideBridge } from "../pyodide/bridge";
import { isPyodide } from "../pyodide/utils";
import { isStaticNotebook } from "../static/static-state";
import { createNetworkRequests } from "./requests-network";
import { createStaticRequests } from "./requests-static";
import { createErrorToastingRequests } from "./requests-toasting";
import { EditRequests, RunRequests } from "./types";

function getRequest(): EditRequests & RunRequests {
  if (isIslands()) {
    // We don't wrap in error toasting, since we don't currently mount
    // the ToastProvider in islands
    return IslandsPyodideBridge.INSTANCE;
  }

  const base = isPyodide()
    ? PyodideBridge.INSTANCE
    : isStaticNotebook()
      ? createStaticRequests()
      : createNetworkRequests();

  return createErrorToastingRequests(base);
}

export const {
  sendComponentValues,
  sendRename,
  sendRestart,
  sendSave,
  sendStdin,
  sendFormat,
  sendInterrupt,
  sendShutdown,
  sendRun,
  sendRunScratchpad,
  sendInstantiate,
  sendDeleteCell,
  sendCodeCompletionRequest,
  saveUserConfig,
  saveAppConfig,
  saveCellConfig,
  sendFunctionRequest,
  sendInstallMissingPackages,
  readCode,
  readSnippets,
  openFile,
  getUsageStats,
  sendListFiles,
  sendCreateFileOrFolder,
  sendDeleteFileOrFolder,
  sendRenameFileOrFolder,
  sendUpdateFile,
  sendFileDetails,
  getRecentFiles,
  getWorkspaceFiles,
  getRunningNotebooks,
  shutdownSession,
  exportAsHTML,
  exportAsMarkdown,
} = getRequest();
