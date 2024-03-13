/* Copyright 2024 Marimo. All rights reserved. */
import { AppConfig, UserConfig } from "../config/config-schema";
import { LayoutType } from "@/components/editor/renderers/types";
import { CellId } from "../cells/ids";
import { CellConfig } from "../cells/types";
import { RequestId } from "./DeferredRequestRegistry";
import { FilePath } from "@/utils/paths";

// Ideally this would be generated from server.py, but for now we just
// manually keep them in sync.

export interface DeleteRequest {
  cellId: CellId;
}

export interface InstantiateRequest {
  objectIds: string[];
  values: unknown[];
}

export interface FormatRequest {
  /**
   * mapping of cell ids to code
   */
  codes: Record<CellId, string>;
  /**
   * line-length
   */
  lineLength: number;
}

export interface FormatResponse {
  /**
   * mapping of formatted cell ids to code
   * response keys are a subset of request keys
   */
  codes: Record<CellId, string>;
}

export interface RenameRequest {
  filename: string | null;
}

export interface RunRequest {
  cellIds: CellId[];
  codes: string[];
}

export interface SaveKernelRequest {
  cellIds: CellId[];
  filename: string;
  codes: string[];
  names: string[];
  layout:
    | {
        type: LayoutType;
        data: unknown;
      }
    | undefined;
  configs: CellConfig[];
}

export interface SetComponentValuesRequest {
  objectIds: string[];
  values: unknown[];
}

export interface CodeCompletionRequest {
  id: RequestId;
  document: string;
  cellId: CellId;
}

export interface SaveUserConfigRequest {
  config: UserConfig;
}

export interface SaveAppConfigRequest {
  config: AppConfig;
}

export interface SaveCellConfigRequest {
  configs: Record<CellId, CellConfig>;
}

export interface SendFunctionRequest {
  functionCallId: RequestId;
  args: unknown;
  namespace: string;
  functionName: string;
}

export interface SendStdin {
  text: string;
}

export interface ValueUpdate {
  objectId: string;
  value: unknown;
}

export interface FileInfo {
  id: string;
  path: FilePath;
  name: string;
  isDirectory: boolean;
  isMarimoFile: boolean;
  children: FileInfo[];
}

export interface FileListRequest {
  path: FilePath | undefined;
}

export interface FileListResponse {
  files: FileInfo[];
  root: FilePath;
}

export interface FileCreateRequest {
  path: FilePath;
  type: "file" | "directory";
  name: string;
  // base64 representation of contents
  contents: string | undefined;
}

export interface FileDeleteRequest {
  path: FilePath;
}

export interface FileUpdateRequest {
  path: FilePath;
  newPath: FilePath;
}

export interface FileOperationResponse {
  success: boolean;
  message: string | undefined;
  info: FileInfo | undefined;
}

export interface FileDetailsResponse {
  file: FileInfo;
  mimeType: string | undefined;
  contents: string | undefined;
}

/**
 * Requests sent to the BE during run/edit mode.
 */
export interface RunRequests {
  sendComponentValues: (valueUpdates: ValueUpdate[]) => Promise<null>;
  sendInstantiate: (request: InstantiateRequest) => Promise<null>;
  sendFunctionRequest: (request: SendFunctionRequest) => Promise<null>;
}

/**
 * Requests sent to the BE during edit mode.
 */
export interface EditRequests {
  sendRename: (filename: string | null) => Promise<null>;
  sendSave: (request: SaveKernelRequest) => Promise<null>;
  sendStdin: (request: SendStdin) => Promise<null>;
  sendRun: (cellIds: CellId[], codes: string[]) => Promise<null>;
  sendInterrupt: () => Promise<null>;
  sendShutdown: () => Promise<null>;
  sendFormat: (request: FormatRequest) => Promise<Record<CellId, string>>;
  sendDeleteCell: (cellId: CellId) => Promise<null>;
  sendCodeCompletionRequest: (request: CodeCompletionRequest) => Promise<null>;
  saveUserConfig: (request: SaveUserConfigRequest) => Promise<null>;
  saveAppConfig: (request: SaveAppConfigRequest) => Promise<null>;
  saveCellConfig: (request: SaveCellConfigRequest) => Promise<null>;
  sendRestart: () => Promise<null>;
  readCode: () => Promise<{ contents: string }>;
  openFile: (request: { path: string }) => Promise<null>;
  // File explorer requests
  sendListFiles: (request: FileListRequest) => Promise<FileListResponse>;
  sendCreateFileOrFolder: (
    request: FileCreateRequest,
  ) => Promise<FileOperationResponse>;
  sendDeleteFileOrFolder: (
    request: FileDeleteRequest,
  ) => Promise<FileOperationResponse>;
  sendRenameFileOrFolder: (
    request: FileUpdateRequest,
  ) => Promise<FileOperationResponse>;
  sendFileDetails: (request: { path: string }) => Promise<FileDetailsResponse>;
}
