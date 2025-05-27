/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { toast } from "@/components/ui/use-toast";
import type { EditRequests, RequestKey, RunRequests } from "./types";
import { Logger } from "@/utils/Logger";
import { prettyError } from "@/utils/errors";

export function createErrorToastingRequests(
  delegate: EditRequests & RunRequests,
): EditRequests & RunRequests {
  const MESSAGES: Record<RequestKey, string> = {
    sendComponentValues: "Failed update value",
    sendModelValue: "Failed to update model value",
    sendInstantiate: "Failed to instantiate",
    sendFunctionRequest: "Failed to send function request",
    sendRestart: "Failed to restart",
    syncCellIds: "Failed to sync cell IDs",
    sendRun: "Failed to run",
    sendRunScratchpad: "Failed to run scratchpad",
    sendRename: "Failed to rename",
    sendSave: "Failed to save",
    sendCopy: "Failed to copy",
    sendInterrupt: "Failed to interrupt",
    sendShutdown: "Failed to shutdown",
    sendFormat: "Failed to format",
    sendDeleteCell: "Failed to delete cell",
    sendCodeCompletionRequest: "Failed to complete code",
    saveUserConfig: "Failed to save user config",
    saveAppConfig: "Failed to save app config",
    saveCellConfig: "Failed to save cell config",
    sendStdin: "Failed to send stdin",
    readCode: "Failed to read code",
    readSnippets: "Failed to fetch snippets",
    previewDatasetColumn: "Failed to fetch data sources",
    previewSQLTable: "Failed to fetch SQL table",
    previewSQLTableList: "Failed to fetch SQL table list",
    previewDataSourceConnection: "Failed to preview data source connection",
    openFile: "Failed to open file",
    getUsageStats: "", // No toast
    sendListFiles: "Failed to list files",
    sendPdb: "Failed to start debug session",
    sendCreateFileOrFolder: "Failed to create file or folder",
    sendDeleteFileOrFolder: "Failed to delete file or folder",
    sendRenameFileOrFolder: "Failed to rename file or folder",
    sendUpdateFile: "Failed to update file",
    sendFileDetails: "Failed to get file details",
    openTutorial: "Failed to open tutorial",
    sendInstallMissingPackages: "Failed to install missing packages",
    getRecentFiles: "Failed to get recent files",
    getWorkspaceFiles: "Failed to get workspace files",
    getRunningNotebooks: "Failed to get running notebooks",
    shutdownSession: "Failed to shutdown session",
    exportAsHTML: "Failed to export HTML",
    exportAsMarkdown: "Failed to export Markdown",
    autoExportAsHTML: "", // No toast
    autoExportAsMarkdown: "", // No toast
    autoExportAsIPYNB: "", // No toast
    addPackage: "Failed to add package",
    removePackage: "Failed to remove package",
    getPackageList: "Failed to get package list",
    listSecretKeys: "Failed to fetch secrets",
    writeSecret: "Failed to write secret",
  };

  const handlers = {} as EditRequests & RunRequests;
  for (const [key, handler] of Object.entries(delegate)) {
    const keyString = key as RequestKey;
    handlers[keyString] = async (...args: any[]) => {
      try {
        return await handler(...args);
      } catch (error) {
        const title = MESSAGES[keyString];
        const message = prettyError(error);
        if (title) {
          toast({
            title: title,
            description: message,
            variant: "danger",
          });
        }
        Logger.error(`Failed to handle request: ${key}`, error);
        // Rethrow the error so that the caller can handle it
        throw error;
      }
    };
  }

  return handlers;
}
