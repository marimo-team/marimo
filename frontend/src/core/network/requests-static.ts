/* Copyright 2024 Marimo. All rights reserved. */
import { toast } from "@/components/ui/use-toast";
import type { EditRequests, RunRequests } from "./types";
import { Logger } from "@/utils/Logger";

export function createStaticRequests(): EditRequests & RunRequests {
  const throwNotInEditMode = () => {
    throw new Error("Unreachable. Expected to be in run mode");
  };

  return {
    sendComponentValues: async () => {
      toast({
        title: "Static notebook",
        description:
          "This notebook is not connected to a kernel. Any interactive elements will not work.",
      });
      Logger.log("Updating UI elements is not supported in static mode");
      return null;
    },
    sendModelValue: async () => {
      Logger.log("Updating model values is not supported in static mode");
      return null;
    },
    sendInstantiate: async () => {
      Logger.log("Viewing as static notebook");
      return null;
    },
    sendFunctionRequest: async () => {
      toast({
        title: "Static notebook",
        description:
          "This notebook is not connected to a kernel. Any interactive elements will not work.",
      });
      Logger.log("Function requests are not supported in static mode");
      return null;
    },
    sendRestart: throwNotInEditMode,
    syncCellIds: throwNotInEditMode,
    sendRun: throwNotInEditMode,
    sendRunScratchpad: throwNotInEditMode,
    sendRename: throwNotInEditMode,
    sendSave: throwNotInEditMode,
    sendCopy: throwNotInEditMode,
    sendInterrupt: throwNotInEditMode,
    sendShutdown: throwNotInEditMode,
    sendFormat: throwNotInEditMode,
    sendDeleteCell: throwNotInEditMode,
    sendCodeCompletionRequest: throwNotInEditMode,
    saveUserConfig: throwNotInEditMode,
    saveAppConfig: throwNotInEditMode,
    saveCellConfig: throwNotInEditMode,
    sendStdin: throwNotInEditMode,
    readCode: throwNotInEditMode,
    readSnippets: throwNotInEditMode,
    previewDatasetColumn: throwNotInEditMode,
    previewSQLTable: throwNotInEditMode,
    previewSQLTableList: throwNotInEditMode,
    previewDataSourceConnection: throwNotInEditMode,
    openFile: throwNotInEditMode,
    getUsageStats: throwNotInEditMode,
    sendListFiles: throwNotInEditMode,
    sendPdb: throwNotInEditMode,
    sendCreateFileOrFolder: throwNotInEditMode,
    sendDeleteFileOrFolder: throwNotInEditMode,
    sendRenameFileOrFolder: throwNotInEditMode,
    sendUpdateFile: throwNotInEditMode,
    sendFileDetails: throwNotInEditMode,
    openTutorial: throwNotInEditMode,
    sendInstallMissingPackages: throwNotInEditMode,
    getRecentFiles: throwNotInEditMode,
    getWorkspaceFiles: throwNotInEditMode,
    getRunningNotebooks: throwNotInEditMode,
    shutdownSession: throwNotInEditMode,
    exportAsHTML: throwNotInEditMode,
    exportAsMarkdown: throwNotInEditMode,
    autoExportAsHTML: throwNotInEditMode,
    autoExportAsMarkdown: throwNotInEditMode,
    autoExportAsIPYNB: throwNotInEditMode,
    addPackage: throwNotInEditMode,
    removePackage: throwNotInEditMode,
    getPackageList: throwNotInEditMode,
    listSecretKeys: throwNotInEditMode,
    writeSecret: throwNotInEditMode,
  };
}
