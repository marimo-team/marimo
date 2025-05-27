/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import type { EditRequests, RunRequests } from "../network/types";
import { Deferred } from "@/utils/Deferred";
import { getMarimoVersion } from "../dom/marimo-tag";
import { getWorkerRPC } from "@/core/wasm/rpc";
import type { OperationMessage } from "../kernel/messages";
import type { JsonString } from "@/utils/json/base64";
import { throwNotImplemented } from "@/utils/functions";
import type { WorkerSchema } from "./worker/worker";
import workerUrl from "./worker/worker.tsx?worker&url";

import { createMarimoFile, parseMarimoIslandApps } from "./parse";
import { Logger } from "@/utils/Logger";
import { store } from "../state/jotai";
import { islandsInitializedAtom } from "./state";

export class IslandsPyodideBridge implements RunRequests, EditRequests {
  /**
   * Lazy singleton instance of the IslandsPyodideBridge.
   */
  static get INSTANCE(): IslandsPyodideBridge {
    const KEY = "_marimo_private_IslandsPyodideBridge";
    if (!window[KEY]) {
      window[KEY] = new IslandsPyodideBridge();
    }
    return window[KEY] as IslandsPyodideBridge;
  }

  private rpc: ReturnType<typeof getWorkerRPC<WorkerSchema>>;
  private messageConsumer:
    | ((message: JsonString<OperationMessage>) => void)
    | undefined;

  public initialized = new Deferred<void>();

  private constructor() {
    // TODO: abstract out into a worker constructor

    // . in front of workerUrl is necessary to make it a relative import
    const url = import.meta.env.DEV
      ? workerUrl
      : makeRelativeWorkerUrl(workerUrl);
    const js = `import ${JSON.stringify(new URL(url, import.meta.url))}`;
    const blob = new Blob([js], { type: "application/javascript" });
    const objURL = URL.createObjectURL(blob);
    const worker = new Worker(
      // eslint-disable-next-line unicorn/relative-url-style
      objURL,
      {
        type: "module",
        // Pass the version to the worker
        /* @vite-ignore */
        name: getMarimoVersion(),
      },
    );

    worker.addEventListener("error", (e) => {
      // Fallback to cleaning up created object URL
      URL.revokeObjectURL(objURL);
    });

    // Create the RPC
    this.rpc = getWorkerRPC<WorkerSchema>(worker);

    // Listeners
    const apps = parseMarimoIslandApps();
    this.rpc.addMessageListener("ready", () => {
      for (const app of apps) {
        Logger.debug("Starting session for app", app.id);
        const file = createMarimoFile(app);
        Logger.debug(file);
        this.startSession({
          code: file,
          appId: app.id,
        });
      }
    });
    this.rpc.addMessageListener("initialized", () => {
      store.set(islandsInitializedAtom, true);
      this.initialized.resolve();
    });
    this.rpc.addMessageListener("initializedError", ({ error }) => {
      store.set(islandsInitializedAtom, error);
      this.initialized.reject(new Error(error));
    });
    this.rpc.addMessageListener("kernelMessage", ({ message }) => {
      this.messageConsumer?.(message);
    });
  }

  async startSession(opts: { code: string; appId: string }) {
    await this.rpc.proxy.request.startSession(opts);
  }

  consumeMessages(consumer: (message: JsonString<OperationMessage>) => void) {
    this.messageConsumer = consumer;
    this.rpc.proxy.send.consumerReady({});
  }

  sendComponentValues: RunRequests["sendComponentValues"] = async (
    request,
  ): Promise<null> => {
    await this.putControlRequest(request);
    return null;
  };

  sendInstantiate: RunRequests["sendInstantiate"] = async (
    request,
  ): Promise<null> => {
    return null;
  };

  sendFunctionRequest: RunRequests["sendFunctionRequest"] = async (
    request,
  ): Promise<null> => {
    await this.putControlRequest(request);
    return null;
  };

  sendRun: EditRequests["sendRun"] = async (request): Promise<null> => {
    await this.rpc.proxy.request.loadPackages(request.codes.join("\n"));
    await this.putControlRequest(request);
    return null;
  };

  sendModelValue: RunRequests["sendModelValue"] = async (request) => {
    await this.putControlRequest(request);
    return null;
  };

  getUsageStats = throwNotImplemented;
  sendRename = throwNotImplemented;
  sendSave = throwNotImplemented;
  sendCopy = throwNotImplemented;
  sendRunScratchpad = throwNotImplemented;
  sendStdin = throwNotImplemented;
  sendInterrupt = throwNotImplemented;
  sendShutdown = throwNotImplemented;
  sendFormat = throwNotImplemented;
  sendDeleteCell = throwNotImplemented;
  sendInstallMissingPackages = throwNotImplemented;
  sendCodeCompletionRequest = throwNotImplemented;
  saveUserConfig = throwNotImplemented;
  saveAppConfig = throwNotImplemented;
  saveCellConfig = throwNotImplemented;
  sendRestart = throwNotImplemented;
  syncCellIds = throwNotImplemented;
  readCode = throwNotImplemented;
  readSnippets = throwNotImplemented;
  previewDatasetColumn = throwNotImplemented;
  previewSQLTable = throwNotImplemented;
  previewSQLTableList = throwNotImplemented;
  previewDataSourceConnection = throwNotImplemented;
  openFile = throwNotImplemented;
  sendListFiles = throwNotImplemented;
  sendPdb = throwNotImplemented;
  sendCreateFileOrFolder = throwNotImplemented;
  sendDeleteFileOrFolder = throwNotImplemented;
  sendRenameFileOrFolder = throwNotImplemented;
  sendUpdateFile = throwNotImplemented;
  sendFileDetails = throwNotImplemented;
  openTutorial = throwNotImplemented;
  exportAsHTML = throwNotImplemented;
  exportAsMarkdown = throwNotImplemented;
  autoExportAsHTML = throwNotImplemented;
  autoExportAsMarkdown = throwNotImplemented;
  autoExportAsIPYNB = throwNotImplemented;
  addPackage = throwNotImplemented;
  removePackage = throwNotImplemented;
  getPackageList = throwNotImplemented;
  getRecentFiles = throwNotImplemented;
  getWorkspaceFiles = throwNotImplemented;
  getRunningNotebooks = throwNotImplemented;
  shutdownSession = throwNotImplemented;
  listSecretKeys = throwNotImplemented;
  writeSecret = throwNotImplemented;

  private async putControlRequest(operation: object) {
    await this.rpc.proxy.request.bridge({
      functionName: "put_control_request",
      payload: operation,
    });
  }
}

function makeRelativeWorkerUrl(url: string) {
  return url.startsWith("./")
    ? url
    : url.startsWith("/")
      ? `.${url}`
      : `./${url}`;
}
