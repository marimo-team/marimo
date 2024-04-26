/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  EditRequests,
  InstantiateRequest,
  RunRequests,
  SendFunctionRequest,
  ValueUpdate,
} from "../network/types";
import { Deferred } from "@/utils/Deferred";
import { getMarimoVersion } from "../dom/marimo-tag";
import { getWorkerRPC } from "@/core/pyodide/rpc";
import { OperationMessage } from "../kernel/messages";
import { JsonString } from "@/utils/json/base64";
import { CellId } from "@/core/cells/ids";
import { throwNotImplemented } from "@/utils/functions";
import type { WorkerSchema } from "./worker/worker";

import { createMarimoFile, parseMarimoIslandApps } from "./parse";
import { Logger } from "@/utils/Logger";

export class IslandsPyodideBridge implements RunRequests, EditRequests {
  /**
   * Lazy singleton instance of the IslandsPyodideBridge.
   */
  private static _instance: IslandsPyodideBridge | undefined;
  public static get INSTANCE() {
    if (!IslandsPyodideBridge._instance) {
      IslandsPyodideBridge._instance = new IslandsPyodideBridge();
    }
    return IslandsPyodideBridge._instance;
  }

  private rpc: ReturnType<typeof getWorkerRPC<WorkerSchema>>;
  private messageConsumer:
    | ((message: JsonString<OperationMessage>) => void)
    | undefined;

  public initialized = new Deferred<void>();

  private constructor() {
    // TODO: abstract out into a worker constructor
    // Must be tsx so that Vite gives it the correct MIME type
    const js = `import ${JSON.stringify(new URL("worker/worker.tsx", import.meta.url))}`;
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
    this.rpc.addMessageListener("ready", () => {
      const apps = parseMarimoIslandApps();
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
      this.initialized.resolve();
    });
    this.rpc.addMessageListener("initializedError", ({ error }) => {
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

  sendRename = throwNotImplemented;
  sendSave = throwNotImplemented;
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
  readCode = throwNotImplemented;
  readSnippets = throwNotImplemented;
  openFile = throwNotImplemented;
  sendListFiles = throwNotImplemented;
  sendCreateFileOrFolder = throwNotImplemented;
  sendDeleteFileOrFolder = throwNotImplemented;
  sendRenameFileOrFolder = throwNotImplemented;
  sendUpdateFile = throwNotImplemented;
  sendFileDetails = throwNotImplemented;
  exportHTML = throwNotImplemented;
  getRecentFiles = throwNotImplemented;
  getWorkspaceFiles = throwNotImplemented;
  getRunningNotebooks = throwNotImplemented;
  shutdownSession = throwNotImplemented;

  private async putControlRequest(operation: object) {
    await this.rpc.proxy.request.bridge({
      functionName: "put_control_request",
      payload: operation,
    });
  }
}
