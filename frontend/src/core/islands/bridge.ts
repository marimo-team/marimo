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
import { getWorkerRPC } from "./rpc";
import { OperationMessage } from "../kernel/messages";
import { JsonString } from "@/utils/json/base64";
import InlineWorker from "./worker/worker.ts?worker&inline";
import { CellId } from "@/core/cells/ids";
import { throwNotImplemented } from "@/utils/functions";
import { isIslands } from "@/core/islands/utils";

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

  private rpc: ReturnType<typeof getWorkerRPC>;
  private messageConsumer:
    | ((message: JsonString<OperationMessage>) => void)
    | undefined;

  public initialized = new Deferred<void>();

  private constructor() {
    // Create a worker, must be inline to work with CORS restrictions
    const worker = new InlineWorker({
      // Pass the version to the worker
      /* @vite-ignore */
      name: isIslands() ? getMarimoVersion() : "dev",
    });

    // Create the RPC
    this.rpc = getWorkerRPC(worker);

    // Listeners
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
