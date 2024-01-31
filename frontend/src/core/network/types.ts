/* Copyright 2024 Marimo. All rights reserved. */
import { AppConfig, UserConfig } from "../config/config-schema";
import { LayoutType } from "@/components/editor/renderers/types";
import { CellId } from "../cells/ids";
import { CellConfig } from "../cells/types";
import { RequestId } from "./DeferredRequestRegistry";

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

export interface SendDirectoryAutocompleteRequest {
  prefix: string;
}

export interface SendDirectoryAutocompleteResponse {
  directories: string[];
  files: string[];
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

interface ValueUpdate {
  objectId: string;
  value: unknown;
}

export interface FileInfo {
  id: string;
  path: string;
  name: string;
  isDirectory: boolean;
  children: FileInfo[];
}

export interface FileListResponse {
  files: FileInfo[];
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
  sendDirectoryAutocompleteRequest: (
    prefix: string
  ) => Promise<SendDirectoryAutocompleteResponse>;
  sendCodeCompletionRequest: (request: CodeCompletionRequest) => Promise<null>;
  saveUserConfig: (request: SaveUserConfigRequest) => Promise<null>;
  saveAppConfig: (request: SaveAppConfigRequest) => Promise<null>;
  saveCellConfig: (request: SaveCellConfigRequest) => Promise<null>;
  readCode: () => Promise<{ contents: string }>;
  // File explorer requests
  sendListFiles: (request: {
    path: string | undefined;
  }) => Promise<FileListResponse>;
}
