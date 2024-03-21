/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { toast } from "@/components/ui/use-toast";
import { EditRequests, RequestKey, RunRequests } from "./types";
import { Logger } from "@/utils/Logger";
import { prettyError } from "@/utils/errors";

export function createErrorToastingRequests(
  delegate: EditRequests & RunRequests,
): EditRequests & RunRequests {
  const MESSAGES: Record<RequestKey, string> = {
    sendComponentValues: "Failed update value",
    sendInstantiate: "Failed to instantiate",
    sendFunctionRequest: "Failed to send function request",
    sendRestart: "Failed to restart",
    sendRun: "Failed to run",
    sendRename: "Failed to rename",
    sendSave: "Failed to save",
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
    openFile: "Failed to open file",
    sendListFiles: "Failed to list files",
    sendCreateFileOrFolder: "Failed to create file or folder",
    sendDeleteFileOrFolder: "Failed to delete file or folder",
    sendRenameFileOrFolder: "Failed to rename file or folder",
    sendFileDetails: "Failed to get file details",
    sendInstallMissingPackages: "Failed to install missing packages",
  };

  const handlers = {} as EditRequests & RunRequests;
  for (const [key, handler] of Object.entries(delegate)) {
    const keyString = key as RequestKey;
    handlers[keyString] = async (...args: any[]) => {
      try {
        return await handler(...args);
      } catch (error) {
        const message = prettyError(error);
        toast({
          title: MESSAGES[keyString],
          description: message,
          variant: "danger",
        });
        Logger.error(`Failed to handle request: ${key}`, error);
        // Rethrow the error so that the caller can handle it
        throw error;
      }
    };
  }

  return handlers;
}
