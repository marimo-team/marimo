/* Copyright 2024 Marimo. All rights reserved. */
import { IslandsPyodideBridge } from "../islands/bridge";
import { isIslands } from "../islands/utils";
import { PyodideBridge } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import { isStaticNotebook } from "../static/static-state";
import { createNetworkRequests } from "./requests-network";
import { createStaticRequests } from "./requests-static";
import { createErrorToastingRequests } from "./requests-toasting";
import type { EditRequests, RunRequests } from "./types";

function getRequest(): EditRequests & RunRequests {
  if (isIslands()) {
    // We don't wrap in error toasting, since we don't currently mount
    // the ToastProvider in islands
    return IslandsPyodideBridge.INSTANCE;
  }

  const base = isWasm()
    ? PyodideBridge.INSTANCE
    : isStaticNotebook()
      ? createStaticRequests()
      : createNetworkRequests();

  return createErrorToastingRequests(base);
}

export const {
  sendComponentValues,
  sendModelValue,
  sendRename,
  sendRestart,
  syncCellIds,
  sendSave,
  sendCopy,
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
  previewDatasetColumn,
  previewSQLTable,
  previewSQLTableList,
  previewDataSourceConnection,
  openFile,
  getUsageStats,
  sendPdb,
  sendListFiles,
  sendCreateFileOrFolder,
  sendDeleteFileOrFolder,
  sendRenameFileOrFolder,
  sendUpdateFile,
  sendFileDetails,
  openTutorial,
  getRecentFiles,
  getWorkspaceFiles,
  getRunningNotebooks,
  shutdownSession,
  exportAsHTML,
  exportAsMarkdown,
  autoExportAsHTML,
  autoExportAsMarkdown,
  autoExportAsIPYNB,
  addPackage,
  removePackage,
  getPackageList,
  listSecretKeys,
  writeSecret,
} = getRequest();
