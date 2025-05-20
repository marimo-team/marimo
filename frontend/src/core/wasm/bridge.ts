/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { Logger } from "@/utils/Logger";
import type {
  EditRequests,
  ExportAsHTMLRequest,
  ExportAsMarkdownRequest,
  FileCreateResponse,
  FileDeleteResponse,
  FileDetailsResponse,
  FileListResponse,
  FileMoveResponse,
  FileUpdateResponse,
  FormatResponse,
  RunRequests,
  SaveUserConfigurationRequest,
  Snippets,
} from "../network/types";
import type { IReconnectingWebSocket } from "../websocket/types";
import { fallbackFileStore, notebookFileStore } from "./store";
import { isWasm } from "./utils";
import { Deferred } from "@/utils/Deferred";
import { createShareableLink } from "./share";
import { PyodideRouter } from "./router";
import { getMarimoVersion } from "../dom/marimo-tag";
import { getWorkerRPC } from "./rpc";
import { API } from "../network/api";
import { parseUserConfig } from "../config/config-schema";
import { throwNotImplemented } from "@/utils/functions";
import type { WorkerSchema } from "./worker/worker";
import type { SaveWorkerSchema } from "./worker/save-worker";
import { toast } from "@/components/ui/use-toast";
import { generateUUID } from "@/utils/uuid";
import { store } from "../state/jotai";
import { notebookIsRunningAtom } from "../cells/cells";
import { getInitialAppMode, initialMode } from "../mode";
import { wasmInitializationAtom } from "./state";
import { reloadSafe } from "@/utils/reload-safe";

type SaveWorker = ReturnType<
  typeof getWorkerRPC<SaveWorkerSchema>
>["proxy"]["request"];

export class PyodideBridge implements RunRequests, EditRequests {
  static get INSTANCE(): PyodideBridge {
    const KEY = "_marimo_private_PyodideBridge";
    if (!window[KEY]) {
      window[KEY] = new PyodideBridge();
    }
    return window[KEY] as PyodideBridge;
  }

  private rpc!: ReturnType<typeof getWorkerRPC<WorkerSchema>>;
  private saveRpc: SaveWorker | undefined;
  private interruptBuffer?: Uint8Array;
  private messageConsumer: ((message: string) => void) | undefined;

  public initialized = new Deferred<void>();

  private getSaveWorker(): SaveWorker {
    if (initialMode === "read") {
      Logger.debug("Skipping SaveWorker in read-mode");
      return {
        readFile: throwNotImplemented,
        readNotebook: throwNotImplemented,
        saveNotebook: throwNotImplemented,
      };
    }

    // Create save worker
    const saveWorker = new Worker(
      // eslint-disable-next-line unicorn/relative-url-style
      new URL("./worker/save-worker.ts", import.meta.url),
      {
        type: "module",
        // Pass the version to the worker
        /* @vite-ignore */
        name: getMarimoVersion(),
      },
    );

    return getWorkerRPC<SaveWorkerSchema>(saveWorker).proxy.request;
  }

  private constructor() {
    if (!isWasm()) {
      return;
    }

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
    this.rpc = getWorkerRPC<WorkerSchema>(worker);

    // Listeners
    this.rpc.addMessageListener("ready", () => {
      this.startSession();
    });
    this.rpc.addMessageListener("initialized", () => {
      // Wait until the worker is ready to create the save worker
      // By initializing after, we get hits on cached network requests
      this.saveRpc = this.getSaveWorker();
      this.setInterruptBuffer();
      this.initialized.resolve();
    });
    this.rpc.addMessageListener("initializingMessage", ({ message }) => {
      store.set(wasmInitializationAtom, message);
    });
    this.rpc.addMessageListener("initializedError", ({ error }) => {
      // If already resolved, show a toast
      if (this.initialized.status === "resolved") {
        Logger.error(error);
        toast({
          title: "Error initializing",
          description: error,
          variant: "danger",
        });
      }
      this.initialized.reject(new Error(error));
    });
    this.rpc.addMessageListener("kernelMessage", ({ message }) => {
      this.messageConsumer?.(message);
    });
  }

  private async startSession() {
    // Pass the code to the worker
    // If a filename is provided, it will be used to save the file
    // If no filename is provided, the file will not be saved
    const code = await notebookFileStore.readFile();
    const fallbackCode = await fallbackFileStore.readFile();
    const filename = PyodideRouter.getFilename();
    const userConfig = parseUserConfig();

    const queryParameters: Record<string, string | string[]> = {};
    const searchParams = new URLSearchParams(window.location.search);
    for (const key of searchParams.keys()) {
      const value = searchParams.getAll(key);
      queryParameters[key] = value.length === 1 ? value[0] : value;
    }

    await this.rpc.proxy.request.startSession({
      queryParameters: queryParameters,
      code: code || fallbackCode || "",
      filename,
      userConfig: {
        ...userConfig,
        runtime: {
          ...userConfig.runtime,
          // Force auto_instantiate to true if the initial mode is read
          auto_instantiate:
            getInitialAppMode() === "read"
              ? true
              : userConfig.runtime.auto_instantiate,
        },
      },
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

  sendRename: EditRequests["sendRename"] = async ({ filename }) => {
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

  sendSave: EditRequests["sendSave"] = async (request) => {
    if (!this.saveRpc) {
      Logger.warn("Save RPC not initialized");
      return null;
    }

    await this.saveRpc.saveNotebook(request);
    const code = await this.readCode();
    if (code.contents) {
      notebookFileStore.saveFile(code.contents);
      fallbackFileStore.saveFile(code.contents);
    }
    // Also save to the other worker, since this is needed for
    // exporting to HTML
    // Fire-and-forget
    void this.rpc.proxy.request.saveNotebook(request).catch((error) => {
      Logger.error(error);
    });
    return null;
  };

  sendCopy: EditRequests["sendCopy"] = async () => {
    throwNotImplemented();
  };

  sendStdin: EditRequests["sendStdin"] = async (request) => {
    await this.rpc.proxy.request.bridge({
      functionName: "put_input",
      payload: request.text,
    });
    return null;
  };

  sendPdb: EditRequests["sendPdb"] = async () => {
    throwNotImplemented();
  };

  sendRun: EditRequests["sendRun"] = async (request) => {
    await this.rpc.proxy.request.loadPackages(request.codes.join("\n"));

    await this.putControlRequest(request);
    return null;
  };
  sendRunScratchpad: EditRequests["sendRunScratchpad"] = async (request) => {
    await this.rpc.proxy.request.loadPackages(request.code);

    await this.putControlRequest(request);
    return null;
  };
  sendInterrupt: EditRequests["sendInterrupt"] = async () => {
    if (this.interruptBuffer !== undefined) {
      // 2 sends a SIGINT
      this.interruptBuffer[0] = 2;
    }
    return null;
  };
  sendShutdown: EditRequests["sendShutdown"] = async () => {
    window.close();
    return null;
  };
  sendFormat: EditRequests["sendFormat"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "format",
      payload: request,
    });
    return response as FormatResponse;
  };

  sendDeleteCell: EditRequests["sendDeleteCell"] = async (request) => {
    await this.putControlRequest(request);
    return null;
  };

  sendInstallMissingPackages: EditRequests["sendInstallMissingPackages"] =
    async (request) => {
      this.putControlRequest(request);
      return null;
    };
  sendCodeCompletionRequest: EditRequests["sendCodeCompletionRequest"] = async (
    request,
  ) => {
    // Because the Pyodide worker is single-threaded, sending
    // code completion requests while the kernel is running is useless
    // and runs the risk of choking the kernel
    const isRunning = store.get(notebookIsRunningAtom);
    if (!isRunning) {
      await this.rpc.proxy.request.bridge({
        functionName: "code_complete",
        payload: request,
      });
    }
    return null;
  };

  saveUserConfig: EditRequests["saveUserConfig"] = async (request) => {
    await this.rpc.proxy.request.bridge({
      functionName: "save_user_config",
      payload: request,
    });

    return API.post<SaveUserConfigurationRequest>(
      "/kernel/save_user_config",
      request,
      { baseUrl: "/" },
    ).catch((error) => {
      // Just log to the console. It is likely a user who hosts their own web-assembly
      // won't use this.
      Logger.error(error);
      return null;
    });
  };

  saveAppConfig: EditRequests["saveAppConfig"] = async (request) => {
    await this.rpc.proxy.request.bridge({
      functionName: "save_app_config",
      payload: request,
    });
    return null;
  };

  saveCellConfig: EditRequests["saveCellConfig"] = async (request) => {
    await this.putControlRequest(request);
    return null;
  };

  sendRestart = async (): Promise<null> => {
    // Save first
    const code = await this.readCode();
    if (code.contents) {
      notebookFileStore.saveFile(code.contents);
      fallbackFileStore.saveFile(code.contents);
    }
    reloadSafe();
    return null;
  };

  readCode: EditRequests["readCode"] = async () => {
    if (!this.saveRpc) {
      Logger.warn("Save RPC not initialized");
      return { contents: "" };
    }
    const contents = await this.saveRpc.readNotebook();
    return { contents };
  };

  readSnippets: EditRequests["readSnippets"] = async () => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "read_snippets",
      payload: undefined,
    });
    return response as Snippets;
  };

  openFile: EditRequests["openFile"] = async ({ path }) => {
    const url = createShareableLink({
      code: null,
      baseUrl: window.location.origin,
    });
    window.open(url, "_blank");
    return null;
  };

  sendListFiles: EditRequests["sendListFiles"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "list_files",
      payload: request,
    });
    return response as FileListResponse;
  };

  sendComponentValues: RunRequests["sendComponentValues"] = async (request) => {
    await this.putControlRequest({
      ...request,
      token: generateUUID(),
    });
    return null;
  };

  sendInstantiate: RunRequests["sendInstantiate"] = async (request) => {
    return null;
  };

  sendFunctionRequest: RunRequests["sendFunctionRequest"] = async (request) => {
    await this.putControlRequest(request);
    return null;
  };

  sendCreateFileOrFolder: EditRequests["sendCreateFileOrFolder"] = async (
    request,
  ) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "create_file_or_directory",
      payload: request,
    });
    return response as FileCreateResponse;
  };

  sendDeleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"] = async (
    request,
  ) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "delete_file_or_directory",
      payload: request,
    });
    return response as FileDeleteResponse;
  };

  sendRenameFileOrFolder: EditRequests["sendRenameFileOrFolder"] = async (
    request,
  ) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "move_file_or_directory",
      payload: request,
    });
    return response as FileMoveResponse;
  };

  sendUpdateFile: EditRequests["sendUpdateFile"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "update_file",
      payload: request,
    });
    return response as FileUpdateResponse;
  };

  sendFileDetails: EditRequests["sendFileDetails"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "file_details",
      payload: request,
    });
    return response as FileDetailsResponse;
  };

  exportAsHTML: EditRequests["exportAsHTML"] = async (
    request: ExportAsHTMLRequest,
  ) => {
    if (
      process.env.NODE_ENV === "development" ||
      process.env.NODE_ENV === "test"
    ) {
      request.assetUrl = window.location.origin;
    }
    const response = await this.rpc.proxy.request.bridge({
      functionName: "export_html",
      payload: request,
    });
    return response as string;
  };

  exportAsMarkdown: EditRequests["exportAsMarkdown"] = async (
    request: ExportAsMarkdownRequest,
  ) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "export_markdown",
      payload: request,
    });
    return response as string;
  };

  previewDatasetColumn: EditRequests["previewDatasetColumn"] = async (
    request,
  ) => {
    await this.putControlRequest(request);
    return null;
  };

  previewSQLTable: EditRequests["previewSQLTable"] = async (request) => {
    await this.putControlRequest(request);
    return null;
  };

  previewSQLTableList: EditRequests["previewSQLTableList"] = async (
    request,
  ) => {
    await this.putControlRequest(request);
    return null;
  };

  previewDataSourceConnection: EditRequests["previewDataSourceConnection"] =
    async (request) => {
      await this.putControlRequest(request);
      return null;
    };

  sendModelValue: RunRequests["sendModelValue"] = async (request) => {
    await this.putControlRequest(request);
    return null;
  };

  syncCellIds = () => Promise.resolve(null);
  getUsageStats = throwNotImplemented;
  openTutorial = throwNotImplemented;
  getRecentFiles = throwNotImplemented;
  getWorkspaceFiles = throwNotImplemented;
  getRunningNotebooks = throwNotImplemented;
  shutdownSession = throwNotImplemented;
  autoExportAsHTML = throwNotImplemented;
  autoExportAsMarkdown = throwNotImplemented;
  autoExportAsIPYNB = throwNotImplemented;

  addPackage: EditRequests["addPackage"] = async (request) => {
    return this.rpc.proxy.request.addPackage(request);
  };
  removePackage: EditRequests["removePackage"] = async (request) => {
    return this.rpc.proxy.request.removePackage(request);
  };
  getPackageList = async () => {
    const response = await this.rpc.proxy.request.listPackages();
    return response;
  };

  listSecretKeys: EditRequests["listSecretKeys"] = async (request) => {
    await this.putControlRequest(request);
    return null;
  };

  writeSecret: EditRequests["writeSecret"] = async (request) => {
    await this.putControlRequest(request);
    return null;
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

  constructor(private bridge: Pick<PyodideBridge, "consumeMessages">) {}

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

  dispatchEvent = throwNotImplemented;
  reconnect = throwNotImplemented;
  send = throwNotImplemented;

  readyState = WebSocket.OPEN;
  retryCount = 0;
  shouldReconnect = false;

  close() {
    return;
  }
}
