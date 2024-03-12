/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { Logger } from "@/utils/Logger";
import { CellId } from "../cells/ids";
import {
  CodeCompletionRequest,
  EditRequests,
  FileCreateRequest,
  FileDeleteRequest,
  FileDetailsResponse,
  FileListRequest,
  FileListResponse,
  FileOperationResponse,
  FileUpdateRequest,
  FormatRequest,
  FormatResponse,
  InstantiateRequest,
  RunRequests,
  SaveAppConfigRequest,
  SaveCellConfigRequest,
  SaveKernelRequest,
  SaveUserConfigRequest,
  SendFunctionRequest,
  SendStdin,
  ValueUpdate,
} from "../network/types";
import { IReconnectingWebSocket } from "../websocket/types";
import { fallbackFileStore, notebookFileStore } from "./store";
import { isPyodide } from "./utils";
import {
  RawBridge,
  WorkerClientPayload,
  WorkerServerPayload,
} from "./worker/types";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { Deferred } from "@/utils/Deferred";
import InlineWorker from "./worker/worker?worker&inline";
import { UserConfigLocalStorage } from "../config/config-schema";
import { createShareableLink } from "./share";
import { PyodideRouter } from "./router";
import { Paths } from "@/utils/paths";
import { getMarimoVersion } from "../dom/marimo-tag";

export type BridgeFunctionAndPayload = {
  [P in keyof RawBridge]: {
    functionName: P;
    payload: Parameters<RawBridge[P]>[0];
  };
}[keyof RawBridge];

export class PyodideBridge implements RunRequests, EditRequests {
  static INSTANCE = new PyodideBridge();

  private worker!: Worker;
  private interruptBuffer?: Uint8Array;
  private messageConsumer: ((message: string) => void) | undefined;
  private fetcher = new DeferredRequestRegistry<
    BridgeFunctionAndPayload,
    unknown
  >("bridge", async (requestId, request) => {
    this.postMessage({
      type: "call-function",
      id: requestId,
      functionName: request.functionName,
      payload: request.payload,
    });
  });

  public initialized = new Deferred<void>();

  constructor() {
    if (isPyodide()) {
      this.worker = new InlineWorker({
        name: getMarimoVersion(),
      });
      this.worker.onmessage = this.handleWorkerMessage;
      if (crossOriginIsolated) {
        // Pyodide handles interrupts through SharedArrayBuffers, which
        // only work in secure (crossOriginIsolated) contexts
        this.interruptBuffer = new Uint8Array(new SharedArrayBuffer(1));
        this.fetcher.request({
          functionName: "set_interrupt_buffer",
          payload: this.interruptBuffer,
        });
      } else {
        console.warn(
          "Not running in a secure context; interrupts are not available.",
        );
      }
    }
  }
  private setCode = async () => {
    // Pass the code to the worker
    // If a filename is provided, it will be used to save the file
    // If no filename is provided, the file will not be saved
    const code = await notebookFileStore.readFile();
    const fallbackCode = await fallbackFileStore.readFile();
    const filename = PyodideRouter.getFilename();
    this.postMessage({
      type: "set-code",
      code: code,
      fallbackCode: fallbackCode || "",
      filename,
    });
  };

  private handleWorkerMessage = async (
    event: MessageEvent<WorkerClientPayload>,
  ) => {
    if (event.data.type === "ready") {
      await this.setCode();
    }
    if (event.data.type === "initialized") {
      this.initialized.resolve();
    }
    if (event.data.type === "initialized-error") {
      this.initialized.reject(new Error(event.data.error));
    }
    if (event.data.type === "message") {
      this.messageConsumer?.(event.data.message);
    }
    if (event.data.type === "error") {
      Logger.error(event.data.error);
      this.fetcher.reject(event.data.id, new Error(event.data.error));
    }
    if (event.data.type === "response") {
      this.fetcher.resolve(event.data.id, event.data.response);
    }
  };

  private postMessage = (message: WorkerServerPayload) => {
    this.worker.postMessage(message);
  };

  consumeMessages = (consumer: (message: string) => void) => {
    this.messageConsumer = consumer;
    this.postMessage({ type: "start-messages" });
  };

  sendRename = async (filename: string | null): Promise<null> => {
    if (filename === null) {
      return null;
    }
    // Set filename in the URL params,
    // so refreshing the page will keep the filename
    PyodideRouter.setFilename(filename);

    await this.fetcher.request({
      functionName: "rename_file",
      payload: filename,
    });
    return null;
  };

  sendSave = async (request: SaveKernelRequest): Promise<null> => {
    await this.fetcher.request({
      functionName: "save",
      payload: request,
    });
    const code = await this.readCode();
    if (code.contents) {
      fallbackFileStore.saveFile(code.contents);
    }
    return null;
  };

  sendStdin = async (request: SendStdin): Promise<null> => {
    await this.fetcher.request({
      functionName: "put_input",
      payload: request.text,
    });
    return null;
  };

  sendRun = async (cellIds: CellId[], codes: string[]): Promise<null> => {
    await this.fetcher.request({
      functionName: "load_packages",
      payload: codes.join("\n"),
    });

    await this.putControlRequest({
      execution_requests: cellIds.map((cellId, index) => ({
        cell_id: cellId,
        code: codes[index],
      })),
    });
    return null;
  };
  sendInterrupt = async (): Promise<null> => {
    if (this.interruptBuffer !== undefined) {
      // 2 sends a SIGINT
      this.interruptBuffer[0] = 2;
    }
    return null;
  };
  sendShutdown = async (): Promise<null> => {
    window.close();
    return null;
  };
  sendFormat = async (
    request: FormatRequest,
  ): Promise<Record<CellId, string>> => {
    const response = await this.fetcher.request({
      functionName: "format",
      payload: request,
    });
    return (response as FormatResponse).codes;
  };
  sendDeleteCell = async (cellId: CellId): Promise<null> => {
    await this.putControlRequest({
      cell_id: cellId,
    });
    return null;
  };

  sendCodeCompletionRequest = async (
    request: CodeCompletionRequest,
  ): Promise<null> => {
    await this.fetcher.request({
      functionName: "code_complete",
      payload: request,
    });
    return null;
  };

  saveUserConfig = async (request: SaveUserConfigRequest): Promise<null> => {
    UserConfigLocalStorage.set(request.config);
    return null;
  };

  saveAppConfig = async (request: SaveAppConfigRequest): Promise<null> => {
    await this.fetcher.request({
      functionName: "save_app_config",
      payload: request,
    });
    return null;
  };

  saveCellConfig = async (request: SaveCellConfigRequest): Promise<null> => {
    await this.putControlRequest({
      configs: request.configs,
    });
    return null;
  };

  sendRestart = async (): Promise<null> => {
    window.location.reload();
    return null;
  };

  readCode = async (): Promise<{ contents: string }> => {
    const response = await this.fetcher.request({
      functionName: "read_code",
      payload: undefined,
    });
    return response as { contents: string };
  };

  openFile = async (request: { path: string }): Promise<null> => {
    // Open the file in a new tab by file path
    const filename = Paths.basename(request.path);
    const url = createShareableLink({
      code: null,
      baseUrl: window.location.origin,
      filename,
    });
    window.open(url, "_blank");
    return null;
  };

  sendListFiles = async (
    request: FileListRequest,
  ): Promise<FileListResponse> => {
    const response = await this.fetcher.request({
      functionName: "list_files",
      payload: request,
    });
    return response as FileListResponse;
  };
  sendComponentValues = async (valueUpdates: ValueUpdate[]): Promise<null> => {
    await this.putControlRequest({
      ids_and_values: valueUpdates.map((update) => [
        update.objectId,
        update.value,
      ]),
    });
    return null;
  };

  sendInstantiate = async (request: InstantiateRequest): Promise<null> => {
    return null;
  };

  sendFunctionRequest = async (request: SendFunctionRequest): Promise<null> => {
    await this.putControlRequest(request);
    return null;
  };

  sendCreateFileOrFolder = async (
    request: FileCreateRequest,
  ): Promise<FileOperationResponse> => {
    const response = await this.fetcher.request({
      functionName: "create_file_or_directory",
      payload: request,
    });
    return response as FileOperationResponse;
  };

  sendDeleteFileOrFolder = async (
    request: FileDeleteRequest,
  ): Promise<FileOperationResponse> => {
    const response = await this.fetcher.request({
      functionName: "delete_file_or_directory",
      payload: request,
    });
    return response as FileOperationResponse;
  };

  sendRenameFileOrFolder = async (
    request: FileUpdateRequest,
  ): Promise<FileOperationResponse> => {
    const response = await this.fetcher.request({
      functionName: "update_file_or_directory",
      payload: request,
    });
    return response as FileOperationResponse;
  };

  sendFileDetails = async (request: {
    path: string;
  }): Promise<FileDetailsResponse> => {
    const response = await this.fetcher.request({
      functionName: "file_details",
      payload: request,
    });
    return response as FileDetailsResponse;
  };

  private putControlRequest = async (operation: object) => {
    await this.fetcher.request({
      functionName: "put_control_request",
      payload: operation,
    });
  };
}

export class PyodideWebsocket implements IReconnectingWebSocket {
  CONNECTING = WebSocket.CONNECTING;
  OPEN = WebSocket.OPEN;
  CLOSING = WebSocket.CLOSING;
  CLOSED = WebSocket.CLOSED;
  binaryType = "blob" as BinaryType;
  bufferedAmount = 0;
  extensions = "";
  protocol = "";
  url = "";

  onclose = null;
  onerror = null;
  onmessage = null;
  onopen = null;

  openSubscriptions = new Set<() => void>();
  closeSubscriptions = new Set<() => void>();
  messageSubscriptions = new Set<(event: MessageEvent) => void>();
  errorSubscriptions = new Set<(event: Event) => void>();

  constructor(private bridge: PyodideBridge) {}

  private consumeMessages() {
    this.bridge.consumeMessages((message) => {
      this.messageSubscriptions.forEach((callback) => {
        callback({ data: message } as MessageEvent);
      });
    });
  }

  addEventListener(type: unknown, callback: any, options?: unknown): void {
    switch (type) {
      case "open":
        this.openSubscriptions.add(callback);
        // Call open right away
        callback();
        break;
      case "close":
        this.closeSubscriptions.add(callback);
        break;
      case "message":
        this.messageSubscriptions.add(callback);
        // Don't start consuming messages until we have a message listener
        this.consumeMessages();
        break;
      case "error":
        this.errorSubscriptions.add(callback);
        break;
    }
  }

  removeEventListener(type: unknown, callback: any, options?: unknown): void {
    switch (type) {
      case "open":
        this.openSubscriptions.delete(callback);
        break;
      case "close":
        this.closeSubscriptions.delete(callback);
        break;
      case "message":
        this.messageSubscriptions.delete(callback);
        break;
      case "error":
        this.errorSubscriptions.delete(callback);
        break;
    }
  }

  dispatchEvent(event: Event): boolean {
    throw new Error("Method not implemented.");
  }

  readyState = WebSocket.OPEN;
  retryCount = 0;
  shouldReconnect = false;

  reconnect(code?: number | undefined, reason?: string | undefined): void {
    throw new Error("Method not implemented.");
  }

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
    throw new Error("Method not implemented.");
  }

  close() {
    return;
  }
}
