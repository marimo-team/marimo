/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { toast } from "@/components/ui/use-toast";
import { userConfigAtom } from "@/core/config/config";
import { Deferred } from "@/utils/Deferred";
import { throwNotImplemented } from "@/utils/functions";
import { Logger } from "@/utils/Logger";
import { reloadSafe } from "@/utils/reload-safe";
import { generateUUID } from "@/utils/uuid";
import { notebookIsRunningAtom } from "../cells/cells";
import type { CommandMessage } from "../kernel/messages";
import { getMarimoVersion } from "../meta/globals";
import { getInitialAppMode } from "../mode";
import { API } from "../network/api";
import type {
  EditRequests,
  ExportAsHTMLRequest,
  ExportAsMarkdownRequest,
  FileCreateResponse,
  FileDeleteResponse,
  FileDetailsResponse,
  FileListResponse,
  FileMoveResponse,
  FileSearchResponse,
  FileUpdateResponse,
  FormatResponse,
  RunRequests,
  SaveUserConfigurationRequest,
  Snippets,
} from "../network/types";
import { filenameAtom } from "../saving/file-state";
import { store } from "../state/jotai";
import { BasicTransport } from "../websocket/transports/basic";
import type { IConnectionTransport } from "../websocket/transports/transport";
import { PyodideRouter } from "./router";
import { getWorkerRPC } from "./rpc";
import { createShareableLink } from "./share";
import { wasmInitializationAtom } from "./state";
import { fallbackFileStore, notebookFileStore } from "./store";
import { isWasm } from "./utils";
import type { SaveWorkerSchema } from "./worker/save-worker";
import type { WorkerSchema } from "./worker/worker";

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
  private messageConsumer:
    | ((message: MessageEvent<string>) => void)
    | undefined;

  public initialized = new Deferred<void>();

  private getSaveWorker(): SaveWorker {
    if (getInitialAppMode() === "read") {
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
      this.messageConsumer?.(new MessageEvent("message", { data: message }));
    });
  }

  private async startSession() {
    // Pass the code to the worker
    // If a filename is provided, it will be used to save the file
    // If no filename is provided, the file will not be saved

    const code = await notebookFileStore.readFile();
    const fallbackCode = await fallbackFileStore.readFile();
    const filename = store.get(filenameAtom) ?? PyodideRouter.getFilename();
    const userConfig = store.get(userConfigAtom);

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

  attachMessageConsumer(consumer: (message: MessageEvent<string>) => void) {
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

    await this.putControlRequest({
      type: "execute-cells",
      ...request,
    });
    return null;
  };
  sendRunScratchpad: EditRequests["sendRunScratchpad"] = async (request) => {
    await this.rpc.proxy.request.loadPackages(request.code);

    await this.putControlRequest({
      type: "execute-scratchpad",
      ...request,
    });
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
    await this.putControlRequest({
      type: "delete-cell",
      ...request,
    });
    return null;
  };

  sendInstallMissingPackages: EditRequests["sendInstallMissingPackages"] =
    async (request) => {
      this.putControlRequest({
        type: "install-packages",
        ...request,
      });
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
    await this.putControlRequest({
      type: "update-cell-config",
      ...request,
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

  sendSearchFiles: EditRequests["sendSearchFiles"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "search_files",
      payload: request,
    });
    return response as FileSearchResponse;
  };

  sendComponentValues: RunRequests["sendComponentValues"] = async (request) => {
    await this.putControlRequest({
      type: "update-ui-element",
      ...request,
      token: generateUUID(),
    });
    return null;
  };

  sendInstantiate: RunRequests["sendInstantiate"] = async (request) => {
    return null;
  };

  sendFunctionRequest: RunRequests["sendFunctionRequest"] = async (request) => {
    await this.putControlRequest({
      type: "invoke-function",
      ...request,
    });
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
    await this.putControlRequest({
      type: "preview-dataset-column",
      ...request,
    });
    return null;
  };

  previewSQLTable: EditRequests["previewSQLTable"] = async (request) => {
    await this.putControlRequest({
      type: "preview-sql-table",
      ...request,
    });
    return null;
  };

  previewSQLTableList: EditRequests["previewSQLTableList"] = async (
    request,
  ) => {
    await this.putControlRequest({
      type: "list-sql-tables",
      ...request,
    });
    return null;
  };

  previewDataSourceConnection: EditRequests["previewDataSourceConnection"] =
    async (request) => {
      await this.putControlRequest({
        type: "list-data-source-connection",
        ...request,
      });
      return null;
    };

  validateSQL: EditRequests["validateSQL"] = async (request) => {
    await this.putControlRequest({
      type: "validate-sql",
      ...request,
    });
    return null;
  };

  sendModelValue: RunRequests["sendModelValue"] = async (request) => {
    await this.putControlRequest({
      type: "model",
      ...request,
    });
    return null;
  };

  syncCellIds = () => Promise.resolve(null);

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

  getDependencyTree: EditRequests["getDependencyTree"] = async () => {
    // WASM doesn't support dependency trees yet
    return {
      tree: {
        dependencies: [],
        name: "",
        tags: [],
        version: null,
      },
    };
  };

  listSecretKeys: EditRequests["listSecretKeys"] = async (request) => {
    await this.putControlRequest({
      type: "list-secret-keys",
      ...request,
    });
    return null;
  };

  getUsageStats = throwNotImplemented;
  openTutorial = throwNotImplemented;
  getRecentFiles = throwNotImplemented;
  getWorkspaceFiles = throwNotImplemented;
  getRunningNotebooks = throwNotImplemented;
  shutdownSession = throwNotImplemented;
  exportAsPDF = throwNotImplemented;
  autoExportAsHTML = throwNotImplemented;
  autoExportAsMarkdown = throwNotImplemented;
  autoExportAsIPYNB = throwNotImplemented;
  updateCellOutputs = throwNotImplemented;
  writeSecret = throwNotImplemented;
  invokeAiTool = throwNotImplemented;
  clearCache = throwNotImplemented;
  getCacheInfo = throwNotImplemented;
  listStorageEntries = throwNotImplemented;
  downloadStorage = throwNotImplemented;

  private async putControlRequest(operation: CommandMessage) {
    await this.rpc.proxy.request.bridge({
      functionName: "put_control_request",
      payload: operation,
    });
  }
}

export function createPyodideConnection(): IConnectionTransport {
  return BasicTransport.withProducerCallback((callback) => {
    PyodideBridge.INSTANCE.attachMessageConsumer(callback);
  });
}
