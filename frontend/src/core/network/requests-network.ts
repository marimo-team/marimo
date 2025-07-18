/* Copyright 2024 Marimo. All rights reserved. */

import { once } from "lodash-es";
import { getRuntimeManager } from "../runtime/config";
import { store } from "../state/jotai";
import { API, createClientWithRuntimeManager } from "./api";
import { isConnectedAtom, waitForConnectionOpen } from "./connection";
import type { EditRequests, RunRequests } from "./types";

const { handleResponse, handleResponseReturnNull } = API;

export function createNetworkRequests(): EditRequests & RunRequests {
  const getClient = once(() => {
    const runtimeManager = getRuntimeManager();
    return createClientWithRuntimeManager(runtimeManager);
  });

  return {
    sendComponentValues: (request) => {
      return getClient()
        .POST("/api/kernel/set_ui_element_value", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendModelValue: (request) => {
      return getClient()
        .POST("/api/kernel/set_model_value", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendRestart: () => {
      return getClient()
        .POST("/api/kernel/restart_session")
        .then(handleResponseReturnNull);
    },
    syncCellIds: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/kernel/sync/cell_ids", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendRename: (request) => {
      return getClient()
        .POST("/api/kernel/rename", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendSave: (request) => {
      return getClient()
        .POST("/api/kernel/save", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponseReturnNull);
    },
    sendCopy: (request) => {
      return getClient()
        .POST("/api/kernel/copy", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponseReturnNull);
    },
    sendFormat: (request) => {
      return getClient()
        .POST("/api/kernel/format", {
          body: request,
        })
        .then(handleResponse);
    },
    sendInterrupt: () => {
      return getClient()
        .POST("/api/kernel/interrupt")
        .then(handleResponseReturnNull);
    },
    sendShutdown: () => {
      return getClient()
        .POST("/api/kernel/shutdown")
        .then(handleResponseReturnNull);
    },
    sendRun: async (request) => {
      // Rather than waiting, we just drop all sendRun requests if the connection is not open.
      // Otherwise we can get into a weird state of sending requests for cells that no longer exist.
      if (!store.get(isConnectedAtom)) {
        return null;
      }
      return getClient()
        .POST("/api/kernel/run", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendRunScratchpad: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/kernel/scratchpad/run", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendInstantiate: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/kernel/instantiate", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendDeleteCell: (request) => {
      return getClient()
        .POST("/api/kernel/delete", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendCodeCompletionRequest: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/kernel/code_autocomplete", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    saveUserConfig: (request) => {
      return getClient()
        .POST("/api/kernel/save_user_config", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    saveAppConfig: (request) => {
      return getClient()
        .POST("/api/kernel/save_app_config", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponseReturnNull);
    },
    saveCellConfig: (request) => {
      return getClient()
        .POST("/api/kernel/set_cell_config", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendFunctionRequest: (request) => {
      return getClient()
        .POST("/api/kernel/function_call", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendStdin: (request) => {
      return getClient()
        .POST("/api/kernel/stdin", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendInstallMissingPackages: (request) => {
      return getClient()
        .POST("/api/kernel/install_missing_packages", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    readCode: async () => {
      await waitForConnectionOpen();
      return getClient().POST("/api/kernel/read_code").then(handleResponse);
    },
    readSnippets: async () => {
      await waitForConnectionOpen();
      return getClient()
        .GET("/api/documentation/snippets")
        .then(handleResponse);
    },
    previewDatasetColumn: (request) => {
      return getClient()
        .POST("/api/datasources/preview_column", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    previewSQLTable: (request) => {
      return getClient()
        .POST("/api/datasources/preview_sql_table", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    previewSQLTableList: (request) => {
      return getClient()
        .POST("/api/datasources/preview_sql_table_list", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    previewDataSourceConnection: (request) => {
      return getClient()
        .POST("/api/datasources/preview_datasource_connection", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    openFile: async (request) => {
      await waitForConnectionOpen();
      await getClient()
        .POST("/api/files/open", {
          body: request,
        })
        .then(handleResponseReturnNull);
      return null;
    },
    getUsageStats: async () => {
      await waitForConnectionOpen();
      return getClient().GET("/api/usage").then(handleResponse);
    },
    sendPdb: (request) => {
      return getClient()
        .POST("/api/kernel/pdb/pm", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendListFiles: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/files/list_files", {
          body: request,
        })
        .then(handleResponse);
    },
    sendCreateFileOrFolder: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/files/create", {
          body: request,
        })
        .then(handleResponse);
    },
    sendDeleteFileOrFolder: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/files/delete", {
          body: request,
        })
        .then(handleResponse);
    },
    sendRenameFileOrFolder: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/files/move", {
          body: request,
        })
        .then(handleResponse);
    },
    sendUpdateFile: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/files/update", {
          body: request,
        })
        .then(handleResponse);
    },
    sendFileDetails: async (request) => {
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/files/file_details", {
          body: request,
        })
        .then(handleResponse);
    },
    openTutorial: (request) => {
      return getClient()
        .POST("/api/home/tutorial/open", {
          body: request,
        })
        .then(handleResponse);
    },
    getRecentFiles: () => {
      return getClient().POST("/api/home/recent_files").then(handleResponse);
    },
    getWorkspaceFiles: (request) => {
      return getClient()
        .POST("/api/home/workspace_files", {
          body: request,
        })
        .then(handleResponse);
    },
    getRunningNotebooks: () => {
      return getClient()
        .POST("/api/home/running_notebooks")
        .then(handleResponse);
    },
    shutdownSession: (request) => {
      return getClient()
        .POST("/api/home/shutdown_session", {
          body: request,
        })
        .then(handleResponse);
    },
    exportAsHTML: async (request) => {
      if (
        process.env.NODE_ENV === "development" ||
        process.env.NODE_ENV === "test"
      ) {
        request.assetUrl = window.location.origin;
      }
      return getClient()
        .POST("/api/export/html", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponse);
    },
    exportAsMarkdown: async (request) => {
      return getClient()
        .POST("/api/export/markdown", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponse);
    },
    autoExportAsHTML: async (request) => {
      return getClient()
        .POST("/api/export/auto_export/html", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    autoExportAsMarkdown: async (request) => {
      return getClient()
        .POST("/api/export/auto_export/markdown", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    autoExportAsIPYNB: async (request) => {
      return getClient()
        .POST("/api/export/auto_export/ipynb", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    addPackage: (request) => {
      return getClient()
        .POST("/api/packages/add", {
          body: request,
        })
        .then(handleResponse);
    },
    removePackage: (request) => {
      return getClient()
        .POST("/api/packages/remove", {
          body: request,
        })
        .then(handleResponse);
    },
    getPackageList: async () => {
      // If the sidebar is already open, it may try to load before the session has been initialized
      await waitForConnectionOpen();
      return getClient().GET("/api/packages/list").then(handleResponse);
    },
    getDependencyTree: async () => {
      // If the sidebar is already open, it may try to load before the session has been initialized
      await waitForConnectionOpen();
      return getClient().GET("/api/packages/tree").then(handleResponse);
    },
    listSecretKeys: async (request) => {
      // If the sidebar is already open, it may try to load before the session has been initialized
      await waitForConnectionOpen();
      return getClient()
        .POST("/api/secrets/keys", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    writeSecret: async (request) => {
      return getClient()
        .POST("/api/secrets/create", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    invokeAiTool: async (request) => {
      return getClient()
        .POST("/api/ai/invoke_tool", {
          body: request,
        })
        .then(handleResponse);
    },
  };
}
