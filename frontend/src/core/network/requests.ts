/* Copyright 2023 Marimo. All rights reserved. */
import { CellId } from "../model/ids";
import { API } from "./api";
import {
  CodeCompletionRequest,
  DeleteRequest,
  FormatResponse,
  FormatRequest,
  InstantiateRequest,
  RenameRequest,
  RunRequest,
  SaveKernelRequest,
  SendDirectoryAutocompleteRequest,
  SendDirectoryAutocompleteResponse,
  SetComponentValuesRequest,
  SaveUserConfigRequest,
  SaveAppConfigRequest,
  SaveCellConfigRequest,
  SendFunctionRequest,
} from "./types";
import { invariant } from "@/utils/invariant";

interface ValueUpdate {
  objectId: string;
  value: unknown;
}

export function sendComponentValues(valueUpdates: ValueUpdate[]) {
  const objectIds = [];
  const values = [];
  for (const update of valueUpdates) {
    objectIds.push(update.objectId);
    values.push(update.value);
  }

  return API.post<SetComponentValuesRequest>("/kernel/set_ui_element_value/", {
    objectIds: objectIds,
    values: values,
  });
}

export function sendRename(filename: string | null) {
  return API.post<RenameRequest>("/kernel/rename/", {
    filename: filename,
  });
}

export function sendSave(request: SaveKernelRequest) {
  // Validate same length
  invariant(
    request.codes.length === request.names.length,
    "cell codes and names must be the same length"
  );
  invariant(
    request.codes.length === request.configs.length,
    "cell codes and configs must be the same length"
  );

  return API.post<SaveKernelRequest>("/kernel/save/", request);
}

export function sendFormat(codes: Record<CellId, string>) {
  return API.post<FormatRequest, FormatResponse>("/kernel/format/", {
    codes: codes,
  }).then((res) => res.codes);
}

export function sendInterrupt() {
  return API.post("/kernel/interrupt/", {});
}

export function sendShutdown() {
  return API.post("/kernel/shutdown/", {});
}

export function sendRun(cellId: CellId, code: string) {
  return sendRunMultiple([cellId], [code]);
}

export function sendInstantiate(request: InstantiateRequest) {
  // Validate same length
  invariant(
    request.objectIds.length === request.values.length,
    "must be the same length"
  );

  return API.post<InstantiateRequest>("/kernel/instantiate/", request);
}

export function sendRunMultiple(cellIds: CellId[], codes: string[]) {
  // Validate same length
  invariant(cellIds.length === codes.length, "must be the same length");

  return API.post<RunRequest>("/kernel/run/", {
    cellIds: cellIds,
    codes: codes,
  });
}

export function sendDeleteCell(cellId: CellId) {
  return API.post<DeleteRequest>("/kernel/delete/", {
    cellId: cellId,
  });
}

export async function sendDirectoryAutocompleteRequest(prefix: string) {
  return API.post<
    SendDirectoryAutocompleteRequest,
    SendDirectoryAutocompleteResponse
  >("/kernel/directory_autocomplete/", {
    prefix: prefix,
  });
}

export async function sendCodeCompletionRequest(
  request: CodeCompletionRequest
) {
  return API.post<CodeCompletionRequest>("/kernel/code_autocomplete/", request);
}

export function saveUserConfig(request: SaveUserConfigRequest) {
  return API.post<SaveUserConfigRequest>("/kernel/save_user_config/", request);
}

export function saveAppConfig(request: SaveAppConfigRequest) {
  return API.post<SaveAppConfigRequest>("/kernel/save_app_config/", request);
}

export function saveCellConfig(request: SaveCellConfigRequest) {
  return API.post<SaveCellConfigRequest>("/kernel/set_cell_config/", request);
}

export function sendFunctionRequest(request: SendFunctionRequest) {
  return API.post<SendFunctionRequest>("/kernel/function/", request);
}
