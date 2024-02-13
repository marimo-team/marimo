/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { Logger } from "@/utils/Logger";
import { CellId } from "../cells/ids";
import {
  CodeCompletionRequest,
  EditRequests,
  FileListResponse,
  FormatRequest,
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
import { bootstrap } from "./bootstrap";
import type { PyodideInterface } from "pyodide";
import { fileStore } from "./store";
import { invariant } from "@/utils/invariant";
import { isPyodide } from "./utils";

interface RawBridge {
  put_control_request(operation: string): Promise<void>;
  put_input(input: string): Promise<void>;
  interrupt(): Promise<void>;
  code_complete(request: string): Promise<string>;
  read_code(): Promise<{ contents: string }>;
  format(request: string): Promise<{ codes: Record<CellId, string> }>;
  save(request: string): Promise<string>;
  save_app_config(request: string): Promise<string>;
  rename_file(request: string): Promise<string>;
  list_files(request: string): Promise<FileListResponse>;
  file_details(request: string): Promise<string>;
  create_file_or_directory(request: string): Promise<string>;
  delete_file_or_directory(request: string): Promise<string>;
  update_file_or_directory(request: string): Promise<string>;
  [Symbol.asyncIterator](): AsyncIterator<string>;
}

export class PyodideBridge implements RunRequests, EditRequests {
  static INSTANCE = new PyodideBridge();

  private context: Promise<{
    bridge: RawBridge;
    pyodide: PyodideInterface;
  }> | null = null;

  constructor() {
    if (isPyodide()) {
      this.context = bootstrap();
    }
  }

  initialize = async () => {
    this.context = bootstrap();
    await this.context;
  };

  consumeMessages = (consumer: (message: string) => void) => {
    let done = false;

    const runForever = async () => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        if (done) {
          return;
        }
        const bridge = await this.bridge;
        for await (const message of bridge) {
          consumer(message);
        }
      }
    };

    void runForever();

    return () => {
      done = true;
    };
  };

  sendRename = async (filename: string | null): Promise<null> => {
    if (filename === null) {
      return null;
    }
    const bridge = await this.bridge;
    await bridge.rename_file(filename);
    return null;
  };

  sendSave = async (request: SaveKernelRequest): Promise<null> => {
    const bridge = await this.bridge;
    await bridge.save(JSON.stringify(request));
    const code = await bridge.read_code();
    if (code.contents) {
      fileStore.saveFile(code.contents);
    }
    return null;
  };

  sendStdin = async (request: SendStdin): Promise<null> => {
    const bridge = await this.bridge;
    await bridge.put_input(request.text);
    return null;
  };

  sendRun = async (cellIds: CellId[], codes: string[]): Promise<null> => {
    await this.putControlRequest({
      execution_requests: cellIds.map((cellId, index) => ({
        cell_id: cellId,
        code: codes[index],
      })),
    });
    return null;
  };
  sendInterrupt = async (): Promise<null> => {
    const bridge = await this.bridge;
    await bridge.interrupt();
    return null;
  };
  sendShutdown = async (): Promise<null> => {
    window.close();
    return null;
  };
  sendFormat = async (
    request: FormatRequest,
  ): Promise<Record<CellId, string>> => {
    const bridge = await this.bridge;
    const response = await bridge.format(JSON.stringify(request));
    return response.codes;
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
    const bridge = await this.bridge;
    await bridge.code_complete(JSON.stringify(request));
    return null;
  };
  saveUserConfig = (request: SaveUserConfigRequest): Promise<null> => {
    throw new Error("Method not implemented.");
  };
  saveAppConfig = async (request: SaveAppConfigRequest): Promise<null> => {
    const bridge = await this.bridge;
    await bridge.save_app_config(JSON.stringify(request));
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
    const bridge = await this.bridge;
    const response = await bridge.read_code();
    return response;
  };
  openFile = (request: { path: string }): Promise<null> => {
    throw new Error("Method not implemented.");
  };
  sendListFiles = async (request: {
    path: string | undefined;
  }): Promise<FileListResponse> => {
    const bridge = await this.bridge;
    const response = await bridge.list_files(JSON.stringify(request));
    return response;
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
    await this.putControlRequest({
      function_call: request,
    });
    return null;
  };

  private putControlRequest = async (operation: object) => {
    const bridge = await this.bridge;
    bridge.put_control_request(JSON.stringify(operation));
  };

  private get bridge() {
    invariant(this.context, "Bridge context is not initialized");
    return this.context.then((context) => context.bridge);
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
        Logger.debug("[js] message", message);
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
