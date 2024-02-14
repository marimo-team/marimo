/* Copyright 2024 Marimo. All rights reserved. */
import type { RequestId } from "@/core/network/DeferredRequestRegistry";
import type {
  CodeCompletionRequest,
  FileListRequest,
  FileListResponse,
  FormatRequest,
  FormatResponse,
  SaveAppConfigRequest,
  SaveKernelRequest,
} from "../../network/types";

export interface RawBridge {
  put_control_request(operation: object): Promise<string>;
  put_input(input: string): Promise<string>;
  interrupt(): Promise<string>;
  code_complete(request: CodeCompletionRequest): Promise<string>;
  read_code(): Promise<{ contents: string }>;
  format(request: FormatRequest): Promise<FormatResponse>;
  save(request: SaveKernelRequest): Promise<string>;
  save_app_config(request: SaveAppConfigRequest): Promise<string>;
  rename_file(request: string): Promise<string>;
  list_files(request: FileListRequest): Promise<FileListResponse>;
  file_details(request: string): Promise<string>;
  create_file_or_directory(request: string): Promise<string>;
  delete_file_or_directory(request: string): Promise<string>;
  update_file_or_directory(request: string): Promise<string>;
  load_packages(request: string): Promise<string>;
  [Symbol.asyncIterator](): AsyncIterator<string>;
}

export type SerializedBridge = {
  [P in keyof RawBridge]: RawBridge[P] extends (
    payload: string,
  ) => Promise<unknown>
    ? (payload: string) => Promise<string>
    : RawBridge[P];
};

export type WorkerServerPayload =
  | {
      type: "start-messages";
    }
  | {
      type: "set-code";
      code: string;
    }
  | {
      type: "call-function";
      id: RequestId;
      functionName: keyof RawBridge | "load_packages";
      payload: {} | undefined | null;
    };

export type WorkerClientPayload =
  | {
      type: "response";
      id: RequestId;
      response: unknown;
    }
  | {
      type: "ready";
    }
  | {
      type: "initialized";
    }
  | {
      type: "error";
      id: RequestId;
      error: string;
    }
  | {
      type: "message";
      message: string;
    };
