/* Copyright 2023 Marimo. All rights reserved. */
import { AppConfig, UserConfig } from "../config/config";
import { LayoutType } from "@/editor/renderers/types";
import { CellId } from "../../core/model/ids";
import { CellConfig } from "../model/cells";
import { RequestId } from "./DeferredRequestRegistry";

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
