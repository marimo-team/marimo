/* Copyright 2024 Marimo. All rights reserved. */
import { API, marimoClient } from "./api";
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
    sendRestart: () => {
      return marimoClient
        .POST("/api/kernel/restart_session")
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
    openFile: async (request) => {
      await marimoClient
        .POST("/api/kernel/open", {
          body: request,
        })
        .then(handleResponseReturnNull);
      await marimoClient
        .POST("/api/kernel/restart_session")
        .then(handleResponseReturnNull);
      window.location.reload();
      return null;
    },
    getUsageStats: () => {
      return marimoClient.GET("/api/usage").then(handleResponse);
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
  };
}
