/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import type { UserConfig } from "@/core/config/config-schema";
import type { OperationMessage } from "@/core/kernel/messages";
import type { JsonString } from "@/utils/json/base64";
import type {
  CodeCompletionRequest,
  CopyNotebookRequest,
  ExportAsHTMLRequest,
  FileCreateRequest,
  FileCreateResponse,
  FileDeleteRequest,
  FileDeleteResponse,
  FileDetailsResponse,
  FileListRequest,
  FileListResponse,
  FileMoveRequest,
  FileMoveResponse,
  FileUpdateRequest,
  FileUpdateResponse,
  FormatRequest,
  FormatResponse,
  SaveAppConfigurationRequest,
  SaveNotebookRequest,
  SaveUserConfigurationRequest,
  Snippets,
} from "../../network/types";

export interface WasmController {
  /**
   * Prepare the wasm environment
   * @param opts.version - The marimo version
   */
  bootstrap(opts: {
    version: string;
    pyodideVersion: string;
  }): Promise<PyodideInterface>;
  /**
   * Mount the filesystem
   * @param opts.code - The code to mount
   * @param opts.filename - The filename to mount, if any
   */
  mountFilesystem(opts: {
    code: string;
    filename: string | null;
  }): Promise<{ code: string; filename: string }>;
  /**
   * Start the session
   * @param opts.code - The code to start with
   * @param opts.fallbackCode - The code to fallback to
   * @param opts.filename - The filename to start with
   */
  startSession(opts: {
    queryParameters: Record<string, string | string[]>;
    code: string;
    filename: string | null;
    userConfig: UserConfig;
    onMessage: (message: JsonString<OperationMessage>) => void;
  }): Promise<SerializedBridge>;
}

export interface RawBridge {
  put_control_request(operation: object): Promise<string>;
  put_input(input: string): Promise<string>;
  code_complete(request: CodeCompletionRequest): Promise<string>;
  read_code(): Promise<{ contents: string }>;
  read_snippets(): Promise<Snippets>;
  format(request: FormatRequest): Promise<FormatResponse>;
  save(request: SaveNotebookRequest): Promise<string>;
  copy(request: CopyNotebookRequest): Promise<string>;
  save_app_config(request: SaveAppConfigurationRequest): Promise<string>;
  save_user_config(request: SaveUserConfigurationRequest): Promise<null>;
  rename_file(request: string): Promise<string>;
  list_files(request: FileListRequest): Promise<FileListResponse>;
  file_details(request: { path: string }): Promise<FileDetailsResponse>;
  create_file_or_directory(
    request: FileCreateRequest,
  ): Promise<FileCreateResponse>;
  delete_file_or_directory(
    request: FileDeleteRequest,
  ): Promise<FileDeleteResponse>;
  move_file_or_directory(request: FileMoveRequest): Promise<FileMoveResponse>;
  update_file(request: FileUpdateRequest): Promise<FileUpdateResponse>;
  load_packages(request: string): Promise<string>;
  read_file(request: string): Promise<string>;
  set_interrupt_buffer(request: Uint8Array): Promise<string>;
  export_html(request: ExportAsHTMLRequest): Promise<string>;
  export_markdown(request: ExportAsHTMLRequest): Promise<string>;
}

export type SerializedBridge = {
  [P in keyof RawBridge]: RawBridge[P] extends (
    payload: string,
  ) => Promise<unknown>
    ? (payload: string) => Promise<string>
    : RawBridge[P];
};
