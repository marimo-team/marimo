/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { getWorkerRPC } from "@/core/wasm/rpc";
import { Deferred } from "@/utils/Deferred";
import { throwNotImplemented } from "@/utils/functions";
import type { JsonString } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import type { OperationMessage } from "../kernel/messages";
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
    | ((message: JsonString<OperationMessage>) => void)
    | undefined;
  private readonly store: typeof defaultStore;
  private readonly root: Document | Element;
  private readonly autoStartSessions: boolean;

  public initialized = new Deferred<void>();

  constructor(config: IslandsBridgeConfig = {}) {
    Logger.debug("IslandsPyodideBridge: Initializing bridge", {
      hasCustomFactory: !!config.workerFactory,
      hasCustomStore: !!config.store,
      hasCustomRoot: !!config.root,
      autoStartSessions: config.autoStartSessions ?? true,
    });

    this.store = config.store || defaultStore;
    this.root = config.root || document;
    this.autoStartSessions = config.autoStartSessions ?? true;

    try {
      // Create worker using factory
      const factory = config.workerFactory || new DefaultWorkerFactory();
      const worker = factory.create();
      Logger.debug("IslandsPyodideBridge: Worker created successfully");

      // Create the RPC
      this.rpc = getWorkerRPC<WorkerSchema>(worker);
      Logger.debug("IslandsPyodideBridge: RPC initialized");

      // Set up message listeners
      this.setupMessageListeners();
      Logger.debug("IslandsPyodideBridge: Message listeners setup complete");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      Logger.error("Failed to initialize IslandsPyodideBridge:", message);
      this.initialized.reject(
        new Error(`Bridge initialization failed: ${message}`),
      );
      throw error;
    }
  }

  /**
   * Sets up message listeners for worker communication
   */
  private setupMessageListeners(): void {
    this.rpc.addMessageListener("ready", () => {
      Logger.debug("IslandsPyodideBridge: Worker ready");
      if (this.autoStartSessions) {
        this.startSessionsForAllApps();
      }
    });

    this.rpc.addMessageListener("initialized", () => {
      Logger.log("IslandsPyodideBridge: Islands initialized successfully");
      this.store.set(islandsInitializedAtom, true);
      this.initialized.resolve();
    });

    this.rpc.addMessageListener(
      "initializedError",
      ({ error }: { error: string }) => {
        Logger.error("IslandsPyodideBridge: Initialization error:", error);
        this.store.set(islandsInitializedAtom, error);
        this.initialized.reject(new Error(error));
      },
    );

    this.rpc.addMessageListener(
      "kernelMessage",
      ({ message }: { message: JsonString<OperationMessage> }) => {
        this.messageConsumer?.(message);
      },
    );
  }

  /**
   * Starts sessions for all apps found in the DOM
   */
  private startSessionsForAllApps(): void {
    try {
      const apps = parseMarimoIslandApps(this.root);
      for (const app of apps) {
        Logger.debug("Starting session for app", app.id);
        const file = createMarimoFile(app);
        Logger.debug(file);
        this.startSession({
          code: file,
          appId: app.id,
        }).catch((error) => {
          Logger.error(`Failed to start session for app ${app.id}:`, error);
        });
      }
    } catch (error) {
      Logger.error("Failed to parse and start island apps:", error);
    }
  }

  /**
   * Starts a new Python session for an app
   */
  async startSession(opts: { code: string; appId: string }): Promise<void> {
    try {
      await this.rpc.proxy.request.startSession(opts);
    } catch (error) {
      Logger.error(`Failed to start session for app ${opts.appId}:`, error);
      throw error;
    }
  }

  /**
   * Sets up a consumer for kernel messages
   */
  consumeMessages(
    consumer: (message: JsonString<OperationMessage>) => void,
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
    try {
      await this.putControlRequest(request);
      return null;
    } catch (error) {
      Logger.error("Failed to send component values:", error);
      throw error;
    }
  };

  sendInstantiate: RunRequests["sendInstantiate"] = async (): Promise<null> => {
    return null;
  };

  sendFunctionRequest: RunRequests["sendFunctionRequest"] = async (
    request,
  ): Promise<null> => {
    try {
      await this.putControlRequest(request);
      return null;
    } catch (error) {
      Logger.error("Failed to send function request:", error);
      throw error;
    }
  };

  sendModelValue: RunRequests["sendModelValue"] = async (request) => {
    try {
      await this.putControlRequest(request);
      return null;
    } catch (error) {
      Logger.error("Failed to send model value:", error);
      throw error;
    }
  };

  // ============================================================================
  // EditRequests Implementation
  // ============================================================================

  sendRun: EditRequests["sendRun"] = async (request): Promise<null> => {
    try {
      await this.rpc.proxy.request.loadPackages(request.codes.join("\n"));
      await this.putControlRequest(request);
      return null;
    } catch (error) {
      Logger.error("Failed to run cell:", error);
      throw error;
    }
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
  syncCellIds = throwNotImplemented;
  readCode = throwNotImplemented;
  readSnippets = throwNotImplemented;
  previewDatasetColumn = throwNotImplemented;
  previewSQLTable = throwNotImplemented;
  previewSQLTableList = throwNotImplemented;
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
  exportAsMarkdown = throwNotImplemented;
  autoExportAsHTML = throwNotImplemented;
  autoExportAsMarkdown = throwNotImplemented;
  autoExportAsIPYNB = throwNotImplemented;
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

  /**
   * Sends a control request to the Python kernel
   */
  private async putControlRequest(operation: object): Promise<void> {
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
 * Global singleton instance for backward compatibility.
 *
 * @deprecated Use `new IslandsPyodideBridge()` directly for better testability
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
