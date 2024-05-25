/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "../cells/ids";
import { API } from "./api";
import type {
  CodeCompletionRequest,
  DeleteRequest,
  FormatResponse,
  FormatRequest,
  InstantiateRequest,
  RenameRequest,
  RunRequest,
  SaveKernelRequest,
  SetComponentValuesRequest,
  SaveUserConfigRequest,
  SaveAppConfigRequest,
  SaveCellConfigRequest,
  SendFunctionRequest,
  RunRequests,
  EditRequests,
  SendStdin,
  SendInstallMissingPackages,
  FileListResponse,
  FileCreateRequest,
  FileOperationResponse,
  FileDeleteRequest,
  FileUpdateRequest,
  FileDetailsResponse,
  FileMoveRequest,
  SnippetsResponse,
  RecentFilesResponse,
  WorkspaceFilesResponse,
  RunningNotebooksResponse,
  ShutdownSessionRequest,
  ExportAsHTMLRequest,
  UsageResponse,
  ExportAsMarkdownRequest,
  WorkspaceFilesRequest,
} from "./types";
import { invariant } from "@/utils/invariant";

export function createNetworkRequests(): EditRequests & RunRequests {
  return {
    sendComponentValues: (valueUpdates) => {
      const objectIds: string[] = [];
      const values: unknown[] = [];
      for (const update of valueUpdates) {
        objectIds.push(update.objectId);
        values.push(update.value);
      }

      return API.post<SetComponentValuesRequest>(
        "/kernel/set_ui_element_value",
        {
          objectIds: objectIds,
          values: values,
        },
      );
    },
    sendRestart: () => {
      return API.post("/kernel/restart_session", {});
    },
    sendRename: (filename: string | null) => {
      return API.post<RenameRequest>("/kernel/rename", {
        filename: filename,
      });
    },
    sendSave: (request: SaveKernelRequest) => {
      // Validate same length
      invariant(
        request.cellIds.length === request.codes.length,
        "cell ids and codes must be the same length",
      );
      invariant(
        request.codes.length === request.names.length,
        "cell ids and names must be the same length",
      );
      invariant(
        request.codes.length === request.configs.length,
        "cell ids and configs must be the same length",
      );

      return API.post<SaveKernelRequest>("/kernel/save", request);
    },
    sendFormat: (request: FormatRequest) => {
      return API.post<FormatRequest, FormatResponse>(
        "/kernel/format",
        request,
      ).then((res) => res.codes);
    },
    sendInterrupt: () => {
      return API.post("/kernel/interrupt", {});
    },
    sendShutdown: () => {
      return API.post("/kernel/shutdown", {});
    },
    sendRun: (cellIds: CellId[], codes: string[]) => {
      // Validate same length
      invariant(cellIds.length === codes.length, "must be the same length");

      return API.post<RunRequest>("/kernel/run", {
        cellIds: cellIds,
        codes: codes,
      });
    },
    sendRunScratchpad: (cellIds: CellId[], codes: string[]) => {
      // Validate same lengths
      invariant(cellIds.length === codes.length, "must be the same length");

      return API.post<RunRequest>("/kernel/run_scratchpad", {
        cellIds: cellIds,
        codes: codes,
      });
    },
    sendInstantiate: (request: InstantiateRequest) => {
      // Validate same length
      invariant(
        request.objectIds.length === request.values.length,
        "must be the same length",
      );

      return API.post<InstantiateRequest>("/kernel/instantiate", request);
    },
    sendDeleteCell: (cellId) => {
      return API.post<DeleteRequest>("/kernel/delete", {
        cellId: cellId,
      });
    },
    sendCodeCompletionRequest: (request) => {
      return API.post<CodeCompletionRequest>(
        "/kernel/code_autocomplete",
        request,
      );
    },
    saveUserConfig: (request) => {
      return API.post<SaveUserConfigRequest>(
        "/kernel/save_user_config",
        request,
      );
    },
    saveAppConfig: (request) => {
      return API.post<SaveAppConfigRequest>("/kernel/save_app_config", request);
    },
    saveCellConfig: (request) => {
      return API.post<SaveCellConfigRequest>(
        "/kernel/set_cell_config",
        request,
      );
    },
    sendFunctionRequest: (request) => {
      return API.post<SendFunctionRequest>("/kernel/function_call", request);
    },
    sendStdin: (request) => {
      return API.post<SendStdin>("/kernel/stdin", request);
    },
    sendInstallMissingPackages: (request) => {
      return API.post<SendInstallMissingPackages>(
        "/kernel/install_missing_packages",
        request,
      );
    },
    readCode: () => {
      return API.post<{}, { contents: string }>("/kernel/read_code", {});
    },
    readSnippets: () => {
      return API.get<SnippetsResponse>("/documentation/snippets", {});
    },
    openFile: async (request) => {
      await API.post<{ path: string }>("/kernel/open", request);
      await API.post("/kernel/restart_session", {});
      window.location.reload();
      return null;
    },
    getUsageStats: () => {
      return API.get<UsageResponse>("/usage", {});
    },
    sendListFiles: (request) => {
      return API.post<{ path: string | undefined }, FileListResponse>(
        "/files/list_files",
        request,
      );
    },
    sendCreateFileOrFolder: (request) => {
      return API.post<FileCreateRequest, FileOperationResponse>(
        "/files/create",
        request,
      );
    },
    sendDeleteFileOrFolder: (request) => {
      return API.post<FileDeleteRequest, FileOperationResponse>(
        "/files/delete",
        request,
      );
    },
    sendRenameFileOrFolder: (request) => {
      return API.post<FileMoveRequest, FileOperationResponse>(
        "/files/move",
        request,
      );
    },
    sendUpdateFile: (request) => {
      return API.post<FileUpdateRequest, FileOperationResponse>(
        "/files/update",
        request,
      );
    },
    sendFileDetails: (request: { path: string }) => {
      return API.post<{ path: string }, FileDetailsResponse>(
        "/files/file_details",
        request,
      );
    },
    getRecentFiles: () => {
      return API.post<{}, RecentFilesResponse>("/home/recent_files", {});
    },
    getWorkspaceFiles: (request) => {
      return API.post<WorkspaceFilesRequest, WorkspaceFilesResponse>(
        "/home/workspace_files",
        request,
      );
    },
    getRunningNotebooks: () => {
      return API.post<{}, RunningNotebooksResponse>(
        "/home/running_notebooks",
        {},
      );
    },
    shutdownSession: (request: ShutdownSessionRequest) => {
      return API.post("/home/shutdown_session", request);
    },
    exportAsHTML: async (request: ExportAsHTMLRequest) => {
      if (
        process.env.NODE_ENV === "development" ||
        process.env.NODE_ENV === "test"
      ) {
        request.assetUrl = window.location.origin;
      }
      return API.post("/export/html", request);
    },
    exportAsMarkdown: async (request: ExportAsMarkdownRequest) => {
      return API.post("/export/markdown", request);
    },
  };
}
