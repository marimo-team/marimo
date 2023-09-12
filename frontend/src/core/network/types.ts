/* Copyright 2023 Marimo. All rights reserved. */
import { AppConfig, UserConfig } from "../config/config";
import { CellId } from "../../core/model/ids";

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
  cellId: CellId;
  code: string;
}

export interface RunMultipleRequest {
  cellIds: CellId[];
  codes: string[];
}

export interface SaveKernelRequest {
  filename: string;
  codes: string[];
  names: string[];
}

export interface SendDirectoryAutocompleteRequest {
  prefix: string;
}

export interface SendDirectoryAutocompleteResponse {
  status: "ok";
  directories: string[];
  files: string[];
}

export interface SetComponentValuesRequest {
  objectIds: string[];
  values: unknown[];
}

export interface CodeCompletionRequest {
  id: string;
  document: string;
  cellId: CellId;
}

export interface SaveUserConfigRequest {
  config: UserConfig;
}

export interface SaveAppConfigRequest {
  config: AppConfig;
}
