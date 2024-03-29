/* Copyright 2024 Marimo. All rights reserved. */
import { toast } from "@/components/ui/use-toast";
import {
  EditRequests,
  InstantiateRequest,
  RunRequests,
  SendFunctionRequest,
} from "./types";
import { Logger } from "@/utils/Logger";

export function createStaticRequests(): EditRequests & RunRequests {
  const throwNotInEditMode = () => {
    throw new Error("Unreachable. Expected to be in run mode");
  };

  return {
    sendComponentValues: async (valueUpdates) => {
      toast({
        title: "Static notebook",
        description:
          "This notebook is not connected to a kernel. Any interactive elements will not work.",
      });
      Logger.log("Updating UI elements is not supported in static mode");
      return null;
    },
    sendInstantiate: async (request: InstantiateRequest) => {
      Logger.log("Viewing as static notebook");
      return null;
    },
    sendFunctionRequest: async (request: SendFunctionRequest) => {
      toast({
        title: "Static notebook",
        description:
          "This notebook is not connected to a kernel. Any interactive elements will not work.",
      });
      Logger.log("Function requests are not supported in static mode");
      return null;
    },
    sendRestart: throwNotInEditMode,
    sendRun: throwNotInEditMode,
    sendRename: throwNotInEditMode,
    sendSave: throwNotInEditMode,
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
    openFile: throwNotInEditMode,
    sendListFiles: throwNotInEditMode,
    sendCreateFileOrFolder: throwNotInEditMode,
    sendDeleteFileOrFolder: throwNotInEditMode,
    sendRenameFileOrFolder: throwNotInEditMode,
    sendUpdateFile: throwNotInEditMode,
    sendFileDetails: throwNotInEditMode,
    sendInstallMissingPackages: throwNotInEditMode,
  };
}
