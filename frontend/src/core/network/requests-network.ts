/* Copyright 2024 Marimo. All rights reserved. */
import { CellId } from "../cells/ids";
import { API } from "./api";
import { sendRestart } from "./requests";
import {
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
    openFile: async (request) => {
      await API.post<{ path: string }>("/kernel/open", request);
      await sendRestart();
      window.location.reload();
      return null;
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
  };
}
