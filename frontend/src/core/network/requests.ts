/* Copyright 2024 Marimo. All rights reserved. */
import { PyodideBridge } from "../pyodide/bridge";
import { isPyodide } from "../pyodide/utils";
import { isStaticNotebook } from "../static/static-state";
import { createNetworkRequests } from "./requests-network";
import { createStaticRequests } from "./requests-static";
import { createErrorToastingRequests } from "./requests-toasting";

function getRequest() {
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
  sendInstantiate,
  sendDeleteCell,
  sendCodeCompletionRequest,
  saveUserConfig,
  saveAppConfig,
  saveCellConfig,
  sendFunctionRequest,
  sendInstallMissingPackages,
  readCode,
  openFile,
  sendListFiles,
  sendCreateFileOrFolder,
  sendDeleteFileOrFolder,
  sendRenameFileOrFolder,
  sendUpdateFile,
  sendFileDetails,
} = getRequest();
