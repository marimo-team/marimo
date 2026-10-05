/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import { toast } from "@/components/ui/use-toast";
import { userConfigAtom } from "@/core/config/config";
import { serializeBlob } from "@/utils/blob";
import { Deferred } from "@/utils/Deferred";
import { throwNotImplemented } from "@/utils/functions";
import { Logger } from "@/utils/Logger";
import { reloadSafe } from "@/utils/reload-safe";
import { generateUUID } from "@/utils/uuid";
import { createModuleWorker } from "@/utils/worker";
import { notebookIsRunningAtom } from "../cells/cells";
import type { CommandMessage } from "../kernel/messages";
import { getInitialAppMode } from "../mode";
import { API } from "../network/api";
import { withDevAssetUrl } from "../network/export-asset-url";
import type {
  EditRequests,
  EnvironmentInfo,
  ExportAsHTMLRequest,
  ExportAsMarkdownRequest,
  ExportAsScriptRequest,
  ExportedFile,
  FileCopyResponse,
  FileCreateResponse,
  FileDeleteResponse,
  FileDetailsResponse,
  FileListResponse,
  FileRootsResponse,
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
import { getWasmRuntimeConfig } from "./runtime-config";
import { createShareableLink } from "./share";
import { wasmInitStateAtom } from "./state";
import { fallbackFileStore, notebookFileStore } from "./store";
import { isWasm } from "./utils";
import saveWorkerUrl from "./worker/save-worker.ts?worker&url";
import workerUrl from "./worker/worker.ts?worker&url";
import { CUSTOM_CONTROLLER_SUFFIX } from "./worker/constants";
import type { SaveWorkerSchema } from "./worker/save-worker";
import type { WorkerSchema } from "./worker/worker";

type SaveWorker = ReturnType<
  typeof getWorkerRPC<SaveWorkerSchema>
>["proxy"]["request"];

export class PyodideBridge implements RunRequests, EditRequests {
  public static get INSTANCE(): PyodideBridge {
    const KEY = "_marimo_private_PyodideBridge";
    if (!window[KEY]) {
      window[KEY] = new PyodideBridge();
    }
    return window[KEY] as PyodideBridge;
  }

  private rpc!: ReturnType<typeof getWorkerRPC<WorkerSchema>>;
  private saveRpc: SaveWorker | undefined;
  private pendingSessionSave: Promise<unknown> = Promise.resolve();
  private interruptBuffer?: Uint8Array;
  private messageConsumer:
    | ((message: MessageEvent<string>) => void)
    | undefined;

  public initialized = new Deferred<void>();

  private getSaveWorker(): SaveWorker {
    if (getInitialAppMode() === "read") {
      Logger.debug("Using partially disabled SaveWorker in read-mode");
      return {
        readFile: throwNotImplemented,
        readNotebook: async () => (await notebookFileStore.readFile()) ?? "",
        saveNotebook: throwNotImplemented,
      };
    }

    const runtimeConfig = getWasmRuntimeConfig();

    // Create save worker
    const saveWorker = createModuleWorker(
      new URL(saveWorkerUrl, import.meta.url),
      {
        // Pass the optional custom-controller capability to the worker.
        name: getWasmWorkerName(),
      },
    );

    const rpc = getWorkerRPC<SaveWorkerSchema>(saveWorker);
    rpc.send.bootstrap(runtimeConfig);
    return rpc.proxy.request;
  }

  private constructor() {
    if (!isWasm()) {
      return;
    }

    const runtimeConfig = getWasmRuntimeConfig();

    // Create a worker
    const worker = createModuleWorker(new URL(workerUrl, import.meta.url), {
      // Pass the optional custom-controller capability to the worker.
      name: getWasmWorkerName(),
    });

    // Create the RPC
    this.rpc = getWorkerRPC<WorkerSchema>(worker);
    this.rpc.send.bootstrap(runtimeConfig);

    // Listeners
    this.rpc.addMessageListener("ready", () => {
      this.startSession();
    });
    this.rpc.addMessageListener("initialized", () => {
      // Wait until the worker is ready to create the save worker
      // By initializing after, we get hits on cached network requests
      this.saveRpc = this.getSaveWorker();
      this.setInterruptBuffer();
      store.set(wasmInitStateAtom, { kind: "ready" });
      this.initialized.resolve();
    });
    this.rpc.addMessageListener("initializingMessage", ({ message }) => {
      // Only bump the progress label while still loading — if we've already
      // reached "ready" or "error", a late message shouldn't roll us back.
      const current = store.get(wasmInitStateAtom);
      if (current.kind === "loading") {
        store.set(wasmInitStateAtom, { kind: "loading", message });
      }
    });
    this.rpc.addMessageListener("initializedError", ({ error }) => {
      // If already initialized, surface as a toast and leave the deferred /
      // init status alone — the worker is healthy, this is a runtime error.
      if (this.initialized.status === "resolved") {
        Logger.error(error);
        toast({
          title: "Error initializing",
          description: error,
          variant: "danger",
        });
        return;
      }
      store.set(wasmInitStateAtom, { kind: "error", message: error });
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

  public attachMessageConsumer(
    consumer: (message: MessageEvent<string>) => void,
  ) {
    this.messageConsumer = consumer;
    this.rpc.proxy.send.consumerReady({});
  }

  public sendRename: EditRequests["sendRename"] = async ({ filename }) => {
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

  public sendSave: EditRequests["sendSave"] = async (request) => {
    if (!this.saveRpc) {
      Logger.warn("Save RPC not initialized");
      return null;
    }

    const durableSave = this.saveRpc.saveNotebook(request);
    // Generated exports read the session-owned app in the main worker.
    this.pendingSessionSave = this.pendingSessionSave
      .catch(() => undefined)
      .then(async () => {
        await durableSave;
        await this.rpc.proxy.request.saveNotebook(request);
      });
    void this.pendingSessionSave.catch((error) => {
      Logger.error(error);
    });

    await durableSave;
    const code = await this.readCode();
    if (code.contents) {
      notebookFileStore.saveFile(code.contents);
      fallbackFileStore.saveFile(code.contents);
    }
    return null;
  };

  public sendCopy: EditRequests["sendCopy"] = async () => {
    throwNotImplemented();
  };

  public sendStdin: EditRequests["sendStdin"] = async (request) => {
    await this.rpc.proxy.request.bridge({
      functionName: "put_input",
      payload: request.text,
    });
    return null;
  };

  public sendPdb: EditRequests["sendPdb"] = async () => {
    throwNotImplemented();
  };

  public sendSetBreakpoints: EditRequests["sendSetBreakpoints"] = async () => {
    throwNotImplemented();
  };

  public sendRun: EditRequests["sendRun"] = async (request) => {
    await this.rpc.proxy.request.loadPackages(request.codes.join("\n"));

    await this.putControlRequest({
      type: "execute-cells",
      ...request,
    });
    return null;
  };
  public sendRunScratchpad: EditRequests["sendRunScratchpad"] = async (
    request,
  ) => {
    await this.rpc.proxy.request.loadPackages(request.code);

    await this.putControlRequest({
      type: "execute-scratchpad",
      ...request,
    });
    return null;
  };
  public sendInterrupt: EditRequests["sendInterrupt"] = async () => {
    if (this.interruptBuffer !== undefined) {
      // 2 sends a SIGINT
      this.interruptBuffer[0] = 2;
    }
    return null;
  };
  public sendShutdown: EditRequests["sendShutdown"] = async () => {
    window.close();
    return null;
  };
  public sendFormat: EditRequests["sendFormat"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "format",
      payload: request,
    });
    return response as FormatResponse;
  };

  public sendDeleteCell: EditRequests["sendDeleteCell"] = async (request) => {
    await this.putControlRequest({
      type: "delete-cell",
      ...request,
    });
    return null;
  };

  public sendInstallMissingPackages: EditRequests["sendInstallMissingPackages"] =
    async (request) => {
      this.putControlRequest({
        type: "install-packages",
        ...request,
      });
      return null;
    };
  public sendCodeCompletionRequest: EditRequests["sendCodeCompletionRequest"] =
    async (request) => {
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

  public saveUserConfig: EditRequests["saveUserConfig"] = async (request) => {
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

  public saveAppConfig: EditRequests["saveAppConfig"] = async (request) => {
    await this.rpc.proxy.request.bridge({
      functionName: "save_app_config",
      payload: request,
    });
    return null;
  };

  public saveCellConfig: EditRequests["saveCellConfig"] = async (request) => {
    await this.putControlRequest({
      type: "update-cell-config",
      ...request,
    });
    return null;
  };

  public sendRestart = async (): Promise<null> => {
    // Save first
    const code = await this.readCode();
    if (code.contents) {
      notebookFileStore.saveFile(code.contents);
      fallbackFileStore.saveFile(code.contents);
    }
    reloadSafe();
    return null;
  };

  public readCode: EditRequests["readCode"] = async () => {
    if (!this.saveRpc) {
      Logger.warn("Save RPC not initialized");
      return { contents: "" };
    }
    const contents = await this.saveRpc.readNotebook();
    return { contents };
  };

  public readSnippets: EditRequests["readSnippets"] = async () => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "read_snippets",
      payload: undefined,
    });
    return response as Snippets;
  };

  public openFile: EditRequests["openFile"] = async ({ path }) => {
    const url = createShareableLink({
      code: null,
      baseUrl: window.location.origin,
    });
    window.open(url, "_blank");
    return null;
  };

  public sendListFiles: EditRequests["sendListFiles"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "list_files",
      payload: request,
    });
    return response as FileListResponse;
  };

  public getFileRoots: EditRequests["getFileRoots"] = async () => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "file_roots",
      payload: undefined,
    });
    return response as FileRootsResponse;
  };

  public sendSearchFiles: EditRequests["sendSearchFiles"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "search_files",
      payload: request,
    });
    return response as FileSearchResponse;
  };

  public sendComponentValues: RunRequests["sendComponentValues"] = async (
    request,
  ) => {
    await this.putControlRequest({
      type: "update-ui-element",
      ...request,
      token: generateUUID(),
    });
    return null;
  };

  public sendInstantiate: RunRequests["sendInstantiate"] = async (request) => {
    return null;
  };

  public sendFunctionRequest: RunRequests["sendFunctionRequest"] = async (
    request,
  ) => {
    await this.putControlRequest({
      type: "invoke-function",
      ...request,
    });
    return null;
  };

  public sendCreateFileOrFolder: EditRequests["sendCreateFileOrFolder"] =
    async (request) => {
      // The WASM RPC boundary can only carry JSON, so we base64-encode the
      // file bytes here. The HTTP transport uses multipart/form-data instead.
      let contents: string | null = null;
      if (request.file) {
        const dataUrl = await serializeBlob(request.file);
        contents = dataUrl.split(",")[1] ?? "";
      }
      const response = await this.rpc.proxy.request.bridge({
        functionName: "create_file_or_directory",
        payload: {
          path: request.path,
          type: request.type,
          name: request.name,
          contents,
        },
      });
      return response as FileCreateResponse;
    };

  public sendDeleteFileOrFolder: EditRequests["sendDeleteFileOrFolder"] =
    async (request) => {
      const response = await this.rpc.proxy.request.bridge({
        functionName: "delete_file_or_directory",
        payload: request,
      });
      return response as FileDeleteResponse;
    };

  public sendCopyFileOrFolder: EditRequests["sendCopyFileOrFolder"] = async (
    request,
  ) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "copy_file_or_directory",
      payload: request,
    });
    return response as FileCopyResponse;
  };

  public sendRenameFileOrFolder: EditRequests["sendRenameFileOrFolder"] =
    async (request) => {
      const response = await this.rpc.proxy.request.bridge({
        functionName: "move_file_or_directory",
        payload: request,
      });
      return response as FileMoveResponse;
    };

  public sendUpdateFile: EditRequests["sendUpdateFile"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "update_file",
      payload: request,
    });
    return response as FileUpdateResponse;
  };

  public sendFileDetails: EditRequests["sendFileDetails"] = async (request) => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "file_details",
      payload: request,
    });
    return response as FileDetailsResponse;
  };

  public exportAsHTML: EditRequests["exportAsHTML"] = async (
    request: ExportAsHTMLRequest,
  ) => {
    await this.pendingSessionSave;
    const response = await this.rpc.proxy.request.bridge({
      functionName: "export_html",
      payload: withDevAssetUrl(request),
    });
    return response as ExportedFile<string>;
  };

  public exportAsMarkdown: EditRequests["exportAsMarkdown"] = async (
    request: ExportAsMarkdownRequest,
  ) => {
    await this.pendingSessionSave;
    const response = await this.rpc.proxy.request.bridge({
      functionName: "export_markdown",
      payload: request,
    });
    return response as ExportedFile<string>;
  };

  public exportAsScript: EditRequests["exportAsScript"] = async (
    request: ExportAsScriptRequest,
  ) => {
    await this.pendingSessionSave;
    const response = await this.rpc.proxy.request.bridge({
      functionName: "export_script",
      payload: request,
    });
    return response as ExportedFile<string>;
  };

  public previewDatasetColumn: EditRequests["previewDatasetColumn"] = async (
    request,
  ) => {
    await this.putControlRequest({
      type: "preview-dataset-column",
      ...request,
    });
    return null;
  };

  public previewSQLTable: EditRequests["previewSQLTable"] = async (request) => {
    await this.putControlRequest({
      type: "preview-sql-table",
      ...request,
    });
    return null;
  };

  public previewSQLTableList: EditRequests["previewSQLTableList"] = async (
    request,
  ) => {
    await this.putControlRequest({
      type: "list-sql-tables",
      ...request,
    });
    return null;
  };

  public previewSQLSchemaList: EditRequests["previewSQLSchemaList"] = async (
    request,
  ) => {
    await this.putControlRequest({
      type: "list-sql-schemas",
      ...request,
    });
    return null;
  };

  public previewDataSourceConnection: EditRequests["previewDataSourceConnection"] =
    async (request) => {
      await this.putControlRequest({
        type: "list-data-source-connection",
        ...request,
      });
      return null;
    };

  public validateSQL: EditRequests["validateSQL"] = async (request) => {
    await this.putControlRequest({
      type: "validate-sql",
      ...request,
    });
    return null;
  };

  public sendModelValue: RunRequests["sendModelValue"] = async (request) => {
    await this.putControlRequest({
      type: "model",
      ...request,
    });
    return null;
  };

  public sendDocumentTransaction = () => Promise.resolve(null);

  public addPackage: EditRequests["addPackage"] = async (request) => {
    return this.rpc.proxy.request.addPackage(request);
  };
  public removePackage: EditRequests["removePackage"] = async (request) => {
    return this.rpc.proxy.request.removePackage(request);
  };
  public getPackageList = async () => {
    const response = await this.rpc.proxy.request.listPackages();
    return response;
  };

  public getSandbox: EditRequests["getSandbox"] = async () => ({
    backend: null,
    manifest: null,
    filename: null,
  });
  public updateManifest: EditRequests["updateManifest"] = async () => {
    throw new Error("Sandboxes are not supported in WebAssembly");
  };
  public syncSandbox: EditRequests["syncSandbox"] = async () => {
    throw new Error("Sandboxes are not supported in WebAssembly");
  };
  public getDependencyTree: EditRequests["getDependencyTree"] = async () => {
    // WASM doesn't support dependency trees yet
    return {
      tree: {
        dependencies: [],
        name: "",
        tags: [],
        version: null,
      },
      context: { kind: "package-manager", name: "micropip" },
    };
  };

  public listSecretKeys: EditRequests["listSecretKeys"] = async (request) => {
    await this.putControlRequest({
      type: "list-secret-keys",
      ...request,
    });
    return null;
  };

  public discoverDataSources: EditRequests["discoverDataSources"] = async (
    request,
  ) => {
    await this.putControlRequest({
      type: "discover-data-sources",
      ...request,
    });
    return null;
  };

  public getUsageStats = throwNotImplemented;
  public getEnvironmentInfo: EditRequests["getEnvironmentInfo"] = async () => {
    const response = await this.rpc.proxy.request.bridge({
      functionName: "get_environment_info",
      payload: undefined,
    });
    return response as EnvironmentInfo;
  };
  public openTutorial = throwNotImplemented;
  public getRecentFiles = throwNotImplemented;
  public getWorkspaceFiles = throwNotImplemented;
  public getRunningNotebooks = throwNotImplemented;
  public shutdownSession = throwNotImplemented;
  public getExportAvailability = throwNotImplemented;
  public installExportRequirements = throwNotImplemented;
  public exportAsIPYNB = throwNotImplemented;
  public exportAsPDF = throwNotImplemented;
  public autoExportAsHTML = throwNotImplemented;
  public autoExportAsMarkdown = throwNotImplemented;
  public autoExportAsIPYNB = throwNotImplemented;
  public updateCellOutputs = throwNotImplemented;
  public writeSecret = throwNotImplemented;
  public invokeAiTool = throwNotImplemented;
  public clearCache = throwNotImplemented;
  public getCacheInfo = throwNotImplemented;
  public listStorageEntries = throwNotImplemented;
  public downloadStorage = throwNotImplemented;

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

// Compose the worker name. The optional "::controller" suffix tells
// getController.ts that the host page provides a custom /wasm/controller.js
// and that the dynamic import should be attempted. Hosts opt in by setting
// `window.__MARIMO_HAS_WASM_CONTROLLER__ = true` before
// PyodideBridge/worker initialization.
export function getWasmWorkerName(): string {
  const hasCustomController =
    typeof window !== "undefined" &&
    (window as unknown as { __MARIMO_HAS_WASM_CONTROLLER__?: boolean })
      .__MARIMO_HAS_WASM_CONTROLLER__ === true;
  return `marimo${hasCustomController ? CUSTOM_CONTROLLER_SUFFIX : ""}`;
}
