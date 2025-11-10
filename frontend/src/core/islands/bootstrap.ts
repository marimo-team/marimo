/* Copyright 2024 Marimo. All rights reserved. */

import { toast } from "@/components/ui/use-toast";
import { ISLAND_CSS_CLASSES, ISLAND_TAG_NAMES } from "@/core/islands/constants";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { initializePlugins } from "@/plugins/plugins";
import { Functions } from "@/utils/functions";
import { safeExtractSetUIElementMessageBuffers } from "@/utils/json/base64";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { Logger } from "@/utils/Logger";
import {
  createNotebookActions,
  notebookAtom,
  notebookReducer,
} from "../cells/cells";
import type { UIElementId } from "../cells/ids";
import { defineCustomElement } from "../dom/defineCustomElement";
import { MarimoValueInputEvent } from "../dom/events";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import {
  handleCellOperation,
  handleKernelReady,
  handleRemoveUIElements,
} from "../kernel/handlers";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import { RuntimeState } from "../kernel/RuntimeState";
import { initialModeAtom } from "../mode";
import type { RequestId } from "../network/DeferredRequestRegistry";
import { requestClientAtom } from "../network/requests";
import { store as defaultStore } from "../state/jotai";
import type { IslandsPyodideBridge } from "./bridge";
import { MarimoIslandElement } from "./components/web-components";
import {
  shouldShowIslandsWarningIndicatorAtom,
  userTriedToInteractWithIslandsAtom,
} from "./state";
import { dismissIslandsLoadingToast, toastIslandsLoading } from "./toast";

// Type for the Jotai store
type Store = typeof defaultStore;

// Type for notebook actions
type NotebookActions = ReturnType<typeof createNotebookActions>;

/**
 * Configuration for the islands bootstrap process
 */
export interface IslandsBootstrapConfig {
  /**
   * The Jotai store to use for state management
   */
  store?: Store;

  /**
   * The bridge to use for communication with Pyodide
   */
  bridge: IslandsPyodideBridge;

  /**
   * The root element to search for islands (defaults to document)
   */
  root?: Document | Element;

  /**
   * Whether to auto-initialize plugins (defaults to true)
   */
  autoInitializePlugins?: boolean;
}

/**
 * IslandsBootstrap manages the initialization and lifecycle of marimo islands.
 *
 * This class encapsulates all the initialization logic for islands mode,
 * making it testable and composable.
 *
 * @example
 * ```ts
 * import { IslandsPyodideBridge } from './bridge';
 *
 * const bridge = new IslandsPyodideBridge();
 * const bootstrap = new IslandsBootstrap({ bridge });
 * await bootstrap.initialize();
 * ```
 */
export class IslandsBootstrap {
  private readonly store: Store;
  private readonly bridge: IslandsPyodideBridge;
  private readonly root: Document | Element;
  private readonly autoInitializePlugins: boolean;
  private actions: NotebookActions | null = null;
  private islands: HTMLElement[] = [];
  private isInitialized = false;

  constructor(config: IslandsBootstrapConfig) {
    this.store = config.store || defaultStore;
    this.bridge = config.bridge;
    this.root = config.root || document;
    this.autoInitializePlugins = config.autoInitializePlugins ?? true;
  }

  /**
   * Main initialization method
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) {
      Logger.warn("IslandsBootstrap already initialized");
      return;
    }

    Logger.log("IslandsBootstrap: Starting initialization");

    try {
      Logger.debug("IslandsBootstrap: Setting up networking");
      this.setupNetworking();

      if (this.autoInitializePlugins) {
        Logger.debug("IslandsBootstrap: Initializing plugins");
        this.initializePluginsStep();
      }

      Logger.debug("IslandsBootstrap: Finding islands in DOM");
      this.findIslands();

      if (this.islands.length === 0) {
        Logger.log("No islands found, skipping initialization");
        return;
      }

      Logger.log(`IslandsBootstrap: Found ${this.islands.length} island(s)`);

      Logger.debug("IslandsBootstrap: Applying styles to islands");
      this.applyStylesToIslands();

      Logger.debug("IslandsBootstrap: Setting up notebook actions");
      this.setupNotebookActions();

      Logger.debug("IslandsBootstrap: Setting up loading indicator");
      this.setupLoadingIndicator();

      Logger.debug("IslandsBootstrap: Setting up message consumer");
      this.setupMessageConsumer();

      Logger.debug("IslandsBootstrap: Setting up user interaction listener");
      this.setupUserInteractionListener();

      Logger.debug("IslandsBootstrap: Starting runtime");
      this.startRuntime();

      this.isInitialized = true;
      Logger.log("IslandsBootstrap: Initialization complete");
    } catch (error) {
      Logger.error("Failed to initialize islands:", error);
      throw error;
    }
  }

  /**
   * Sets up the networking layer
   */
  private setupNetworking(): void {
    this.store.set(requestClientAtom, this.bridge);
    this.store.set(initialModeAtom, "read");
  }

  /**
   * Initializes plugins for rendering static HTML
   */
  private initializePluginsStep(): void {
    initializePlugins();
  }

  /**
   * Finds all island elements in the DOM
   */
  private findIslands(): void {
    this.islands = Array.from(
      this.root.querySelectorAll<HTMLElement>(ISLAND_TAG_NAMES.ISLAND),
    );
  }

  /**
   * Applies CSS classes to islands for styling
   */
  private applyStylesToIslands(): void {
    for (const island of this.islands) {
      island.classList.add(ISLAND_CSS_CLASSES.NAMESPACE);
    }
  }

  /**
   * Sets up the notebook actions for state management
   */
  private setupNotebookActions(): void {
    this.actions = createNotebookActions((action) => {
      this.store.set(notebookAtom, (state: typeof notebookAtom.init) =>
        notebookReducer(state, action),
      );
    });
  }

  /**
   * Sets up the loading indicator that shows when users interact before initialization
   */
  private setupLoadingIndicator(): void {
    this.store.sub(shouldShowIslandsWarningIndicatorAtom, () => {
      const showing = this.store.get(shouldShowIslandsWarningIndicatorAtom);
      if (showing) {
        toastIslandsLoading();
        this.setIslandsOpacity("0.5");
      } else {
        dismissIslandsLoadingToast();
        this.setIslandsOpacity(null);
      }
    });
  }

  /**
   * Sets the opacity of all islands
   */
  private setIslandsOpacity(value: string | null): void {
    for (const island of this.islands) {
      if (value === null) {
        island.style.removeProperty("opacity");
      } else {
        island.style.setProperty("opacity", value);
      }
    }
  }

  /**
   * Sets up the message consumer to handle messages from the Python kernel
   */
  private setupMessageConsumer(): void {
    if (!this.actions) {
      throw new Error("Actions not initialized");
    }

    const actions = this.actions;

    this.bridge.consumeMessages((message) => {
      this.handleMessage(message, actions);
    });
  }

  /**
   * Handles a single message from the kernel
   */
  private handleMessage(message: string, actions: NotebookActions): void {
    try {
      const msg = jsonParseWithSpecialChar(message) as {
        data: any;
      };

      switch (msg.data.op) {
        // Unsupported operations in islands mode
        case "banner":
        case "missing-package-alert":
        case "installing-package-alert":
        case "completion-result":
        case "reload":
        case "update-cell-codes":
        case "update-cell-ids":
        case "focus-cell":
        case "variables":
        case "variable-values":
        case "data-column-preview":
        case "sql-table-preview":
        case "sql-table-list-preview":
        case "datasets":
        case "data-source-connections":
        case "validate-sql-result":
        case "secret-keys-result":
        case "startup-logs":
          return;

        case "kernel-ready":
          handleKernelReady(msg.data, {
            autoInstantiate: true,
            setCells: actions.setCells,
            setLayoutData: Functions.NOOP,
            setAppConfig: Functions.NOOP,
            setCapabilities: Functions.NOOP,
            onError: Logger.error,
          });
          // Define the custom element after kernel is ready
          defineCustomElement(ISLAND_TAG_NAMES.ISLAND, MarimoIslandElement);
          return;

        case "completed-run":
        case "interrupted":
          return;

        case "send-ui-element-message":
          UI_ELEMENT_REGISTRY.broadcastMessage(
            msg.data.ui_element as UIElementId,
            msg.data.message,
            safeExtractSetUIElementMessageBuffers(msg.data),
          );
          return;

        case "remove-ui-elements":
          handleRemoveUIElements(msg.data);
          return;

        case "function-call-result":
          FUNCTIONS_REGISTRY.resolve(
            msg.data.function_call_id as RequestId,
            msg.data,
          );
          return;

        case "cell-op":
          handleCellOperation(msg.data, actions.handleCellMessage);
          return;

        case "alert":
          toast({
            title: msg.data.title,
            description: renderHTML({
              html: msg.data.description,
            }),
            variant: msg.data.variant,
          });
          return;

        case "query-params-append":
          queryParamHandlers.append(msg.data);
          return;

        case "query-params-set":
          queryParamHandlers.set(msg.data);
          return;

        case "query-params-delete":
          queryParamHandlers.delete(msg.data);
          return;

        case "query-params-clear":
          queryParamHandlers.clear();
          return;

        case "reconnected":
        case "cache-cleared":
        case "cache-info-fetched":
          return;

        default:
          // Log unknown message types
          Logger.warn("Unknown message type:", msg.data.op);
          return;
      }
    } catch (error) {
      Logger.error("Failed to handle kernel message:", error);
      // Don't rethrow - we want to continue processing other messages
    }
  }

  /**
   * Sets up listener for user interactions before initialization completes
   */
  private setupUserInteractionListener(): void {
    document.addEventListener(
      MarimoValueInputEvent.TYPE,
      () => {
        this.store.set(userTriedToInteractWithIslandsAtom, true);
      },
      {
        once: true,
      },
    );
  }

  /**
   * Starts the runtime state machine
   */
  private startRuntime(): void {
    RuntimeState.INSTANCE.start(this.bridge.sendComponentValues);
  }

  /**
   * Gets the current islands
   */
  getIslands(): readonly HTMLElement[] {
    return this.islands;
  }

  /**
   * Checks if bootstrap is initialized
   */
  isReady(): boolean {
    return this.isInitialized;
  }

  /**
   * Cleans up resources (for testing)
   */
  destroy(): void {
    this.islands = [];
    this.actions = null;
    this.isInitialized = false;
  }
}
