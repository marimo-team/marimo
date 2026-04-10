/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import { getWorkerRPC } from "@/core/wasm/rpc";
import { Deferred } from "@/utils/Deferred";
import { throwNotImplemented } from "@/utils/functions";
import type { JsonString } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { generateUUID } from "@/utils/uuid";
import type { CommandMessage, NotificationPayload } from "../kernel/messages";
import type { EditRequests, RunRequests } from "../network/types";
import { store as defaultStore } from "../state/jotai";
import { createMarimoFile, parseMarimoIslandApps } from "./parse";
import { islandsInitializedAtom } from "./state";
import type { WorkerSchema } from "./worker/worker";
import type { WorkerFactory } from "./worker-factory";
import { DefaultWorkerFactory } from "./worker-factory";

/**
 * Configuration for creating an IslandsPyodideBridge
 */
export interface IslandsBridgeConfig {
  /**
   * Optional worker factory for creating workers (for testing)
   */
  workerFactory?: WorkerFactory;

  /**
   * Optional Jotai store (for testing)
   */
  store?: typeof defaultStore;

  /**
   * Optional root element for parsing islands (for testing)
   */
  root?: Document | Element;

  /**
   * Whether to auto-start sessions on worker ready (default: true)
   */
  autoStartSessions?: boolean;
}

/**
 * Bridge between the browser and Pyodide worker for islands mode.
 *
 * This class manages communication with a Web Worker that runs Python code
 * via Pyodide, enabling interactive marimo islands.
 *
 * @example
 * ```ts
 * const bridge = new IslandsPyodideBridge();
 * await bridge.initialized;
 * bridge.consumeMessages(message => console.log(message));
 * ```
 */
export class IslandsPyodideBridge implements RunRequests, EditRequests {
  private rpc: ReturnType<typeof getWorkerRPC<WorkerSchema>>;
  private messageConsumer:
    | ((message: JsonString<NotificationPayload>) => void)
    | undefined;
  private readonly store: typeof defaultStore;
  private readonly root: Document | Element;
  private readonly autoStartSessions: boolean;

  public initialized = new Deferred<void>();

  constructor(config: IslandsBridgeConfig = {}) {
    this.store = config.store || defaultStore;
    this.root = config.root || document;
    this.autoStartSessions = config.autoStartSessions ?? true;

    try {
      const factory = config.workerFactory || new DefaultWorkerFactory();
      const worker = factory.create();
      this.rpc = getWorkerRPC<WorkerSchema>(worker);
      this.setupMessageListeners();
    } catch (error) {
      Logger.error("Failed to initialize IslandsPyodideBridge:", error);
      this.initialized.reject(error);
      throw error;
    }
  }

  /**
   * Sets up message listeners for worker communication
   */
  private setupMessageListeners(): void {
    this.rpc.addMessageListener("ready", () => {
      if (this.autoStartSessions) {
        this.startSessionsForAllApps();
      }
    });

    this.rpc.addMessageListener("initialized", () => {
      this.store.set(islandsInitializedAtom, true);
      this.initialized.resolve();
    });

    this.rpc.addMessageListener(
      "initializedError",
      ({ error }: { error: string }) => {
        Logger.error("Islands initialization error:", error);
        this.store.set(islandsInitializedAtom, error);
        this.initialized.reject(new Error(error));
      },
    );

    this.rpc.addMessageListener(
      "kernelMessage",
      ({ message }: { message: JsonString<NotificationPayload> }) => {
        this.messageConsumer?.(message);
      },
    );
  }

  /**
   * Starts sessions for all apps found in the DOM
   */
  private startSessionsForAllApps(): void {
    const apps = parseMarimoIslandApps(this.root);
    Logger.debug(
      `Starting sessions for ${apps.length} app(s):`,
      apps.map((a) => `${a.id} (${a.cells.length} cells)`),
    );
    for (const app of apps) {
      const file = createMarimoFile(app);
      Logger.debug(`App ${app.id} marimo file:\n`, file);
      this.startSession({
        code: file,
        appId: app.id,
      }).catch((error) => {
        Logger.error(`Failed to start session for app ${app.id}:`, error);
      });
    }
  }

  /**
   * Starts a new Python session for an app
   */
  async startSession(opts: { code: string; appId: string }): Promise<void> {
    await this.rpc.proxy.request.startSession(opts);
  }

  /**
   * Sets up a consumer for kernel messages
   */
  consumeMessages(
    consumer: (message: JsonString<NotificationPayload>) => void,
  ): void {
    this.messageConsumer = consumer;
    this.rpc.proxy.send.consumerReady({});
  }

  // ============================================================================
  // RunRequests Implementation
  // ============================================================================

  sendComponentValues: RunRequests["sendComponentValues"] = async (
    request,
  ): Promise<null> => {
    await this.putControlRequest({
      type: "update-ui-element",
      ...request,
      token: generateUUID(),
    });
    return null;
  };

  sendInstantiate: RunRequests["sendInstantiate"] = async (): Promise<null> => {
    return null;
  };

  sendFunctionRequest: RunRequests["sendFunctionRequest"] = async (
    request,
  ): Promise<null> => {
    await this.putControlRequest({
      type: "invoke-function",
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

  // ============================================================================
  // EditRequests Implementation
  // ============================================================================

  sendRun: EditRequests["sendRun"] = async (request): Promise<null> => {
    await this.rpc.proxy.request.loadPackages(request.codes.join("\n"));
    await this.putControlRequest({
      type: "execute-cells",
      ...request,
    });
    return null;
  };

  // ============================================================================
  // Not Implemented (Read-Only Mode)
  // ============================================================================

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
  sendDocumentTransaction = throwNotImplemented;
  readCode = throwNotImplemented;
  readSnippets = throwNotImplemented;
  previewDatasetColumn = throwNotImplemented;
  previewSQLTable = throwNotImplemented;
  previewSQLTableList = throwNotImplemented;
  previewSQLSchemaList = throwNotImplemented;
  previewDataSourceConnection = throwNotImplemented;
  validateSQL = throwNotImplemented;
  openFile = throwNotImplemented;
  sendListFiles = throwNotImplemented;
  sendSearchFiles = throwNotImplemented;
  sendPdb = throwNotImplemented;
  sendCreateFileOrFolder = throwNotImplemented;
  sendDeleteFileOrFolder = throwNotImplemented;
  sendRenameFileOrFolder = throwNotImplemented;
  sendUpdateFile = throwNotImplemented;
  sendFileDetails = throwNotImplemented;
  openTutorial = throwNotImplemented;
  exportAsHTML = throwNotImplemented;
  exportAsIPYNB = throwNotImplemented;
  exportAsMarkdown = throwNotImplemented;
  exportAsPDF = throwNotImplemented;
  autoExportAsHTML = throwNotImplemented;
  autoExportAsMarkdown = throwNotImplemented;
  autoExportAsIPYNB = throwNotImplemented;
  updateCellOutputs = throwNotImplemented;
  addPackage = throwNotImplemented;
  removePackage = throwNotImplemented;
  getPackageList = throwNotImplemented;
  getDependencyTree = throwNotImplemented;
  getRecentFiles = throwNotImplemented;
  getWorkspaceFiles = throwNotImplemented;
  getRunningNotebooks = throwNotImplemented;
  shutdownSession = throwNotImplemented;
  listSecretKeys = throwNotImplemented;
  writeSecret = throwNotImplemented;
  invokeAiTool = throwNotImplemented;
  clearCache = throwNotImplemented;
  getCacheInfo = throwNotImplemented;
  listStorageEntries = throwNotImplemented;
  downloadStorage = throwNotImplemented;

  // The kernel uses msgspec to parse control requests, which requires a 'type'
  // field for discriminated union deserialization.
  private async putControlRequest(operation: CommandMessage): Promise<void> {
    await this.rpc.proxy.request.bridge({
      functionName: "put_control_request",
      payload: operation,
    });
  }

  /**
   * Cleans up resources (for testing)
   */
  destroy(): void {
    // Future: terminate worker if we own it
  }
}

/**
 * Global singleton instance.
 * Use `new IslandsPyodideBridge(config)` in tests for better isolation.
 */
let globalBridgeInstance: IslandsPyodideBridge | null = null;

export function getGlobalBridge(): IslandsPyodideBridge {
  if (!globalBridgeInstance) {
    globalBridgeInstance = new IslandsPyodideBridge();
  }
  return globalBridgeInstance;
}

/**
 * Resets the global bridge instance (for testing)
 */
export function resetGlobalBridge(): void {
  globalBridgeInstance = null;
}
