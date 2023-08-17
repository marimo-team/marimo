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
  RunMultipleRequest,
  SaveKernelRequest,
  SendDirectoryAutocompleteRequest,
  SendDirectoryAutocompleteResponse,
  SetComponentValuesRequest,
  SaveUserConfigRequest,
  SaveAppConfigRequest,
} from "./types";

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

export function sendSave(codes: string[], names: string[], filename: string) {
  return API.post<SaveKernelRequest>("/kernel/save/", {
    codes: codes,
    names: names,
    filename: filename,
  });
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
  return API.post<InstantiateRequest>("/kernel/instantiate/", request);
}

export function sendRunMultiple(cellIds: CellId[], codes: string[]) {
  return API.post<RunMultipleRequest>("/kernel/run/", {
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
  id: string,
  document: string,
  cellId: CellId
) {
  return API.post<CodeCompletionRequest>("/kernel/code_autocomplete/", {
    id: id,
    document: document,
    cellId: cellId,
  });
}

export function saveUserConfig(request: SaveUserConfigRequest) {
  return API.post<SaveUserConfigRequest>("/kernel/save_user_config/", request);
}

export function saveAppConfig(request: SaveAppConfigRequest) {
  return API.post<SaveAppConfigRequest>("/kernel/save_app_config/", request);
}
