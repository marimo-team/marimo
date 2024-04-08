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
  FileMoveRequest,
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
  SendInstallMissingPackages,
  SendStdin,
  SnippetsResponse,
  ValueUpdate,
} from "../network/types";
import { IReconnectingWebSocket } from "../websocket/types";
import { fallbackFileStore, notebookFileStore } from "./store";
import { isPyodide } from "./utils";
import { Deferred } from "@/utils/Deferred";
import { createShareableLink } from "./share";
import { PyodideRouter } from "./router";
import { getMarimoVersion } from "../dom/marimo-tag";
import { getWorkerRPC } from "./rpc";
import { API } from "../network/api";
import { RuntimeState } from "@/core/kernel/RuntimeState";

export class PyodideBridge implements RunRequests, EditRequests {
  static INSTANCE = new PyodideBridge();

  private rpc!: ReturnType<typeof getWorkerRPC>;
  private interruptBuffer?: Uint8Array;
  private messageConsumer: ((message: string) => void) | undefined;

  public initialized = new Deferred<void>();

  constructor() {
    if (isPyodide()) {
      // Create a worker
      const worker = new Worker(
        // eslint-disable-next-line unicorn/relative-url-style
        new URL("./worker/worker.ts", import.meta.url),
        {
          type: "module",
          // Pass the version to the worker
          /* @vite-ignore */
          name: getMarimoVersion(),
        },
      );

      // Create the RPC
      this.rpc = getWorkerRPC(worker);

      // Listeners
      this.rpc.addMessageListener("ready", () => {
        this.startSession();
      });
      this.rpc.addMessageListener("initialized", () => {
        this.setInterruptBuffer();
        this.initialized.resolve();
      });
      this.rpc.addMessageListener("initializedError", ({ error }) => {
        this.initialized.reject(new Error(error));
      });
      this.rpc.addMessageListener("kernelMessage", ({ message }) => {
        this.messageConsumer?.(message);
      });
    }
  }

  private async startSession() {
    // Pass the code to the worker
    // If a filename is provided, it will be used to save the file
    // If no filename is provided, the file will not be saved
    const code = await notebookFileStore.readFile();
    const fallbackCode = await fallbackFileStore.readFile();
    const filename = PyodideRouter.getFilename();

    const queryParameters: Record<string, string | string[]> = {};
    const searchParams = new URLSearchParams(window.location.search);
    for (const key of searchParams.keys()) {
      const value = searchParams.getAll(key);
      queryParameters[key] = value.length === 1 ? value[0] : value;
    }

    await this.rpc.proxy.request.startSession({
      queryParameters: queryParameters,
      code,
      fallbackCode: fallbackCode || "",
      filename,
    });
  }

  private setInterruptBuffer() {
    // Set up the interrupt buffer
    if (crossOriginIsolated) {
      // Pyodide handles interrupts through SharedArrayBuffers, which
      // only work in secure (crossOriginIsolated) contexts
      this.interruptBuffer = new Uint8Array(new SharedArrayBuffer(1));
      this.rpc.proxy.request.setInterruptBuffer(this.interruptBuffer);
    } else {
      Logger.warn(
        "Not running in a secure context; interrupts are not available.",
      );
    }
  }

  consumeMessages(consumer: (message: string) => void) {
    this.messageConsumer = consumer;
    this.rpc.proxy.send.consumerReady({});
  }

  sendRename = async (filename: string | null): Promise<null> => {
    if (filename === null) {
      return null;
    }
    // Set filename in the URL params,
    // so refreshing the page will keep the filename
    PyodideRouter.setFilename(filename);

    await this.rpc.proxy.request.bridge({
      functionName: "rename_file",
      payload: filename,
    });
    return null;
  };

  sendSave = async (request: SaveKernelRequest): Promise<null> => {
    await this.rpc.proxy.request.bridge({
      functionName: "save",
      payload: request,
    });
    const code = await this.readCode();
    if (code.contents) {
      notebookFileStore.saveFile(code.contents);
      fallbackFileStore.saveFile(code.contents);
    }
    return null;
  };

  sendStdin = async (request: SendStdin): Promise<null> => {
    await this.rpc.proxy.request.bridge({
      functionName: "put_input",
      payload: request.text,
    });
    return null;
  };

  sendRun = async (cellIds: CellId[], codes: string[]): Promise<null> => {
    await this.rpc.proxy.request.loadPackages(codes.join("\n"));

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
    const response = await this.rpc.proxy.request.bridge({
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
  sendInstallMissingPackages = async (
    request: SendInstallMissingPackages,
  ): Promise<null> => {
    this.putControlRequest(request);
    return null;
  };
  sendCodeCompletionRequest = async (
    request: CodeCompletionRequest,
  ): Promise<null> => {
    // Because the Pyodide worker is single-threaded, sending
    // code completion requests while the kernel is running is useless
    // and runs the risk of choking the kernel
    if (!RuntimeState.INSTANCE.running()) {
      await this.rpc.proxy.request.bridge({
        functionName: "code_complete",
        payload: request,
      });
    }
    return null;
  };

  saveUserConfig = async (request: SaveUserConfigRequest): Promise<null> => {
    return API.post<SaveUserConfigRequest>(
      "/kernel/save_user_config",
      request,
      { baseUrl: "/" },
    );
  };

  saveAppConfig = async (request: SaveAppConfigRequest): Promise<null> => {
    await this.rpc.proxy.request.bridge({
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
    // Save first
    const code = await this.readCode();
    if (code.contents) {
      notebookFileStore.saveFile(code.contents);
      fallbackFileStore.saveFile(code.contents);
    }
    window.location.reload();
    return null;
  };

  readCode = async (): Promise<{ contents: string }> => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "read_code",
      payload: undefined,
    });
    return response as { contents: string };
  };

  readSnippets = async (): Promise<SnippetsResponse> => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "read_snippets",
      payload: undefined,
    });
    return response as SnippetsResponse;
  };

  openFile = async (request: { path: string }): Promise<null> => {
    const url = createShareableLink({
      code: null,
      baseUrl: window.location.origin,
    });
    window.open(url, "_blank");
    return null;
  };

  sendListFiles = async (
    request: FileListRequest,
  ): Promise<FileListResponse> => {
    const response = await this.rpc.proxy.request.bridge({
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
    const response = await this.rpc.proxy.request.bridge({
      functionName: "create_file_or_directory",
      payload: request,
    });
    return response as FileOperationResponse;
  };

  sendDeleteFileOrFolder = async (
    request: FileDeleteRequest,
  ): Promise<FileOperationResponse> => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "delete_file_or_directory",
      payload: request,
    });
    return response as FileOperationResponse;
  };

  sendRenameFileOrFolder = async (
    request: FileMoveRequest,
  ): Promise<FileOperationResponse> => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "move_file_or_directory",
      payload: request,
    });
    return response as FileOperationResponse;
  };

  sendUpdateFile = async (
    request: FileUpdateRequest,
  ): Promise<FileOperationResponse> => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "update_file",
      payload: request,
    });
    return response as FileOperationResponse;
  };

  sendFileDetails = async (request: {
    path: string;
  }): Promise<FileDetailsResponse> => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "file_details",
      payload: request,
    });
    return response as FileDetailsResponse;
  };

  private async putControlRequest(operation: object) {
    await this.rpc.proxy.request.bridge({
      functionName: "put_control_request",
      payload: operation,
    });
  }
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
