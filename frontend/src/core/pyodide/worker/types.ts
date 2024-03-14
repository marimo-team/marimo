/* Copyright 2024 Marimo. All rights reserved. */
import type {
  CodeCompletionRequest,
  FileCreateRequest,
  FileDeleteRequest,
  FileDetailsResponse,
  FileListRequest,
  FileListResponse,
  FileOperationResponse,
  FileUpdateRequest,
  FormatRequest,
  FormatResponse,
  SaveAppConfigRequest,
  SaveKernelRequest,
} from "../../network/types";

export interface RawBridge {
  put_control_request(operation: object): Promise<string>;
  put_input(input: string): Promise<string>;
  code_complete(request: CodeCompletionRequest): Promise<string>;
  read_code(): Promise<{ contents: string }>;
  format(request: FormatRequest): Promise<FormatResponse>;
  save(request: SaveKernelRequest): Promise<string>;
  save_app_config(request: SaveAppConfigRequest): Promise<string>;
  rename_file(request: string): Promise<string>;
  list_files(request: FileListRequest): Promise<FileListResponse>;
  file_details(request: { path: string }): Promise<FileDetailsResponse>;
  create_file_or_directory(
    request: FileCreateRequest,
  ): Promise<FileOperationResponse>;
  delete_file_or_directory(
    request: FileDeleteRequest,
  ): Promise<FileOperationResponse>;
  update_file_or_directory(
    request: FileUpdateRequest,
  ): Promise<FileOperationResponse>;
  load_packages(request: string): Promise<string>;
  read_file(request: string): Promise<string>;
  set_interrupt_buffer(request: Uint8Array): Promise<string>;
}

export type SerializedBridge = {
  [P in keyof RawBridge]: RawBridge[P] extends (
    payload: string,
  ) => Promise<unknown>
    ? (payload: string) => Promise<string>
    : RawBridge[P];
};
