/* Copyright 2024 Marimo. All rights reserved. */
import { API, marimoClient } from "./api";
import { waitForConnectionOpen } from "./connection";
import type { RunRequests, EditRequests } from "./types";

const { handleResponse, handleResponseReturnNull } = API;

export function createNetworkRequests(): EditRequests & RunRequests {
  return {
    sendComponentValues: (request) => {
      return marimoClient
        .POST("/api/kernel/set_ui_element_value", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendModelValue: (request) => {
      return marimoClient
        .POST("/api/kernel/set_model_value", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendRestart: () => {
      return marimoClient
        .POST("/api/kernel/restart_session")
        .then(handleResponseReturnNull);
    },
    syncCellIds: (request) => {
      return marimoClient
        .POST("/api/kernel/sync/cell_ids", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendRename: (request) => {
      return marimoClient
        .POST("/api/kernel/rename", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendSave: (request) => {
      return marimoClient
        .POST("/api/kernel/save", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponseReturnNull);
    },
    sendCopy: (request) => {
      return marimoClient
        .POST("/api/kernel/copy", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponseReturnNull);
    },
    sendFormat: (request) => {
      return marimoClient
        .POST("/api/kernel/format", {
          body: request,
        })
        .then(handleResponse);
    },
    sendInterrupt: () => {
      return marimoClient
        .POST("/api/kernel/interrupt")
        .then(handleResponseReturnNull);
    },
    sendShutdown: () => {
      return marimoClient
        .POST("/api/kernel/shutdown")
        .then(handleResponseReturnNull);
    },
    sendRun: (request) => {
      return marimoClient
        .POST("/api/kernel/run", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendRunScratchpad: (request) => {
      return marimoClient
        .POST("/api/kernel/scratchpad/run", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendInstantiate: (request) => {
      return marimoClient
        .POST("/api/kernel/instantiate", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendDeleteCell: (request) => {
      return marimoClient
        .POST("/api/kernel/delete", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendCodeCompletionRequest: (request) => {
      return marimoClient
        .POST("/api/kernel/code_autocomplete", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    saveUserConfig: (request) => {
      return marimoClient
        .POST("/api/kernel/save_user_config", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    saveAppConfig: (request) => {
      return marimoClient
        .POST("/api/kernel/save_app_config", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponseReturnNull);
    },
    saveCellConfig: (request) => {
      return marimoClient
        .POST("/api/kernel/set_cell_config", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendFunctionRequest: (request) => {
      return marimoClient
        .POST("/api/kernel/function_call", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendStdin: (request) => {
      return marimoClient
        .POST("/api/kernel/stdin", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendInstallMissingPackages: (request) => {
      return marimoClient
        .POST("/api/kernel/install_missing_packages", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    readCode: () => {
      return marimoClient.POST("/api/kernel/read_code").then(handleResponse);
    },
    readSnippets: () => {
      return marimoClient
        .GET("/api/documentation/snippets")
        .then(handleResponse);
    },
    previewDatasetColumn: (request) => {
      return marimoClient
        .POST("/api/datasources/preview_column", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    previewSQLTable: (request) => {
      return marimoClient
        .POST("/api/datasources/preview_sql_table", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    previewSQLTableList: (request) => {
      return marimoClient
        .POST("/api/datasources/preview_sql_table_list", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    previewDataSourceConnection: (request) => {
      return marimoClient
        .POST("/api/datasources/preview_datasource_connection", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    openFile: async (request) => {
      await marimoClient
        .POST("/api/files/open", {
          body: request,
        })
        .then(handleResponseReturnNull);
      return null;
    },
    getUsageStats: () => {
      return marimoClient.GET("/api/usage").then(handleResponse);
    },
    sendPdb: (request) => {
      return marimoClient
        .POST("/api/kernel/pdb/pm", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    sendListFiles: (request) => {
      return marimoClient
        .POST("/api/files/list_files", {
          body: request,
        })
        .then(handleResponse);
    },
    sendCreateFileOrFolder: (request) => {
      return marimoClient
        .POST("/api/files/create", {
          body: request,
        })
        .then(handleResponse);
    },
    sendDeleteFileOrFolder: (request) => {
      return marimoClient
        .POST("/api/files/delete", {
          body: request,
        })
        .then(handleResponse);
    },
    sendRenameFileOrFolder: (request) => {
      return marimoClient
        .POST("/api/files/move", {
          body: request,
        })
        .then(handleResponse);
    },
    sendUpdateFile: (request) => {
      return marimoClient
        .POST("/api/files/update", {
          body: request,
        })
        .then(handleResponse);
    },
    sendFileDetails: (request) => {
      return marimoClient
        .POST("/api/files/file_details", {
          body: request,
        })
        .then(handleResponse);
    },
    openTutorial: (request) => {
      return marimoClient
        .POST("/api/home/tutorial/open", {
          body: request,
        })
        .then(handleResponse);
    },
    getRecentFiles: () => {
      return marimoClient.POST("/api/home/recent_files").then(handleResponse);
    },
    getWorkspaceFiles: (request) => {
      return marimoClient
        .POST("/api/home/workspace_files", {
          body: request,
        })
        .then(handleResponse);
    },
    getRunningNotebooks: () => {
      return marimoClient
        .POST("/api/home/running_notebooks")
        .then(handleResponse);
    },
    shutdownSession: (request) => {
      return marimoClient
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
      return marimoClient
        .POST("/api/export/html", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponse);
    },
    exportAsMarkdown: async (request) => {
      return marimoClient
        .POST("/api/export/markdown", {
          body: request,
          parseAs: "text",
        })
        .then(handleResponse);
    },
    autoExportAsHTML: async (request) => {
      return marimoClient
        .POST("/api/export/auto_export/html", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    autoExportAsMarkdown: async (request) => {
      return marimoClient
        .POST("/api/export/auto_export/markdown", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    autoExportAsIPYNB: async (request) => {
      return marimoClient
        .POST("/api/export/auto_export/ipynb", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    addPackage: (request) => {
      return marimoClient
        .POST("/api/packages/add", {
          body: request,
        })
        .then(handleResponse);
    },
    removePackage: (request) => {
      return marimoClient
        .POST("/api/packages/remove", {
          body: request,
        })
        .then(handleResponse);
    },
    getPackageList: async () => {
      // If the sidebar is already open, it may try to load before the session has been initialized
      await waitForConnectionOpen();
      return marimoClient.GET("/api/packages/list").then(handleResponse);
    },
    listSecretKeys: async (request) => {
      // If the sidebar is already open, it may try to load before the session has been initialized
      await waitForConnectionOpen();
      return marimoClient
        .POST("/api/secrets/keys", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
    writeSecret: async (request) => {
      return marimoClient
        .POST("/api/secrets/create", {
          body: request,
        })
        .then(handleResponseReturnNull);
    },
  };
}
