/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useAtomValue } from "jotai";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import { NoKernelConnectedError, prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import { useConnectToRuntime } from "../runtime/config";
import { store } from "../state/jotai";
import { isConnectingAtom } from "./connection";
import type { EditRequests, RequestKey, RunRequests } from "./types";

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
    validateSQL: "Failed to validate SQL",
    openFile: "Failed to open file",
    getUsageStats: "", // No toast
    sendListFiles: "Failed to list files",
    sendSearchFiles: "Failed to search files",
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
    exportAsPDF: "Failed to export PDF",
    autoExportAsHTML: "", // No toast
    autoExportAsMarkdown: "", // No toast
    autoExportAsIPYNB: "", // No toast
    updateCellOutputs: "", // No toast
    addPackage: "Failed to add package",
    removePackage: "Failed to remove package",
    getPackageList: "Failed to get package list",
    getDependencyTree: "Failed to get dependency tree",
    listSecretKeys: "Failed to fetch secrets",
    writeSecret: "Failed to write secret",
    invokeAiTool: "Failed to invoke AI tool",
    clearCache: "Failed to clear cache",
    getCacheInfo: "", // No toast
    listStorageEntries: "Failed to list storage entries",
    downloadStorage: "Failed to download storage entry",
  };

  const handlers = {} as EditRequests & RunRequests;
  for (const [key, handler] of Object.entries(delegate)) {
    const keyString = key as RequestKey;
    handlers[keyString] = async (...args: any[]) => {
      try {
        return await handler(...args);
      } catch (error) {
        // Special handling for NoKernelConnectedError error
        if (error instanceof NoKernelConnectedError) {
          // If we are connecting to a kernel, don't show the toast
          const isConnecting = store.get(isConnectingAtom);
          if (isConnecting) {
            return;
          }

          const toastId = toast({
            title: "Kernel Not Connected",
            description:
              "You need to connect to a kernel to perform this action.",
            variant: "default",
            action: <ConnectButton onConnect={() => toastId.dismiss()} />,
          });
          Logger.error(`Failed to handle request: ${key}`, error);
          // Rethrow the error so that the caller can handle it
          throw error;
        }

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

export const ConnectButton: React.FC<{ onConnect: () => void }> = ({
  onConnect,
}) => {
  const connectToRuntime = useConnectToRuntime();
  const isConnecting = useAtomValue(isConnectingAtom);
  return (
    <Button
      size="xs"
      onClick={() => {
        connectToRuntime();
        setTimeout(() => {
          onConnect();
        }, 800);
      }}
      disabled={isConnecting}
    >
      {isConnecting && <Spinner size="small" className="mr-1" />}
      Connect
    </Button>
  );
};
