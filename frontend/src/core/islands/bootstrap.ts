/* Copyright 2026 Marimo. All rights reserved. */

import { toast } from "@/components/ui/use-toast";
import { ISLAND_CSS_CLASSES, ISLAND_TAG_NAMES } from "@/core/islands/constants";
import { renderHTML } from "@/plugins/core/RenderHTML";
import {
  handleWidgetMessage,
  WIDGET_REGISTRY,
} from "@/plugins/impl/anywidget/registry";
import { initializePlugins } from "@/plugins/plugins";
import { Functions } from "@/utils/functions";
import { safeExtractSetUIElementMessageBuffers } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { logNever } from "@/utils/assertNever";
import {
  createNotebookActions,
  notebookAtom,
  notebookReducer,
} from "../cells/cells";
import { followDocument } from "../cells/document";
import { createDocumentModel } from "../notebook/document";
import { defineCustomElement } from "../dom/defineCustomElement";
import { MarimoValueInputEvent } from "../dom/events";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import { createNotebookReplica } from "../notebook/replica";
import {
  handleCellNotificationeration,
  handleKernelReady,
  handleRemoveUIElements,
} from "../kernel/handlers";
import type { NotificationMessage } from "../kernel/messages";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import { RuntimeState } from "../kernel/RuntimeState";
import { initialModeAtom } from "../mode";
import { requestClientAtom } from "../network/requests";
import { store as defaultStore } from "../state/jotai";
import type { IslandsPyodideBridge } from "./bridge";
import { MarimoIslandElement } from "./components/web-components";
import {
  islandsPendingInitialRunsAtom,
  shouldShowIslandsWarningIndicatorAtom,
  userTriedToInteractWithIslandsAtom,
} from "./state";
import { dismissIslandsLoadingToast, toastIslandsLoading } from "./toast";

type Store = typeof defaultStore;
type NotebookActions = ReturnType<typeof createNotebookActions>;

/**
 * Configuration for the islands bootstrap process
 */
export interface IslandsBootstrapConfig {
  bridge: IslandsPyodideBridge;
  store?: Store;
  root?: Document | Element;
  autoInitializePlugins?: boolean;
}

/**
 * Initialize marimo islands: sets up networking, discovers island elements,
 * wires up the message consumer, and starts the runtime.
 */
export async function initializeIslands(
  config: IslandsBootstrapConfig,
): Promise<void> {
  const store = config.store || defaultStore;
  const root = config.root || document;
  const bridge = config.bridge;

  // Setup networking
  store.set(requestClientAtom, bridge);
  store.set(initialModeAtom, "read");
  store.set(islandsPendingInitialRunsAtom, null);

  // Initialize plugins for rendering static HTML
  if (config.autoInitializePlugins !== false) {
    initializePlugins();
  }

  // Find all island elements
  // eslint-disable-next-line prefer-spread
  const islands = Array.from(
    root.querySelectorAll<HTMLElement>(ISLAND_TAG_NAMES.ISLAND),
  );

  if (islands.length === 0) {
    Logger.log("No islands found, skipping initialization");
    return;
  }

  Logger.log(`Initializing ${islands.length} island(s)`);

  // Apply styles
  for (const island of islands) {
    island.classList.add(ISLAND_CSS_CLASSES.NAMESPACE);
  }

  // Setup notebook actions
  const actions = createNotebookActions((action) => {
    store.set(notebookAtom, (state: typeof notebookAtom.init) =>
      notebookReducer(state, action),
    );
  });

  // Loading indicator: dim islands while Pyodide initializes
  store.sub(shouldShowIslandsWarningIndicatorAtom, () => {
    const showing = store.get(shouldShowIslandsWarningIndicatorAtom);
    const currentIslands = root.querySelectorAll<HTMLElement>(
      ISLAND_TAG_NAMES.ISLAND,
    );
    if (showing) {
      toastIslandsLoading();
      for (const island of currentIslands) {
        island.style.setProperty("opacity", "0.5");
      }
    } else {
      dismissIslandsLoadingToast();
      for (const island of currentIslands) {
        island.style.removeProperty("opacity");
      }
    }
  });

  // Each notification names the session that sent it.
  bridge.consumeNotifications((notification, sessionGeneration) => {
    handleNotification(notification, actions, store, sessionGeneration);
  });

  // The notebook's cells follow the managed session's host document.
  const replica = createNotebookReplica(store);
  replica.connect(bridge.notebookBackend, { onNotification: Functions.NOOP });
  const documentModel = createDocumentModel({
    store,
    documentAtom: replica.documentAtom,
    backendAtom: replica.backendAtom,
  });
  const lifetime = new AbortController();
  documentModel.start({ signal: lifetime.signal });
  followDocument({
    store,
    model: documentModel,
    reconcile: actions.reconcileDocument,
    signal: lifetime.signal,
  });

  // Track first user interaction before initialization completes
  document.addEventListener(
    MarimoValueInputEvent.TYPE,
    () => {
      store.set(userTriedToInteractWithIslandsAtom, true);
    },
    { once: true },
  );

  // Start the runtime
  RuntimeState.INSTANCE.start(bridge.sendComponentValues);
}

/** Handles a single notification from the kernel. */
// oxlint-disable-next-line marimo/prefer-object-params
function handleNotification(
  msg: NotificationMessage,
  actions: NotebookActions,
  store: Store,
  sessionGeneration: number,
): void {
  try {
    Logger.debug("Islands received message:", msg.op);

    switch (msg.op) {
      // Unsupported operations in islands mode
      case "banner":
      case "missing-package-alert":
      case "environment-operation":
      case "environment-state":
      case "completion-result":
      case "reload":
      case "focus-cell":
      case "active-line":
      case "variables":
      case "variable-values":
      case "data-column-preview":
      case "sql-table-preview":
      case "sql-table-list-preview":
      case "sql-schema-list-preview":
      case "datasets":
      case "data-source-connections":
      case "data-source-discovery-result":
      case "validate-sql-result":
      case "storage-namespaces":
      case "storage-entries":
      case "storage-download-ready":
      case "secret-keys-result":
      case "startup-logs":
      case "startup-progress":
      case "interrupted":
      case "reconnected":
      case "cache-cleared":
      case "cache-info":
      case "kernel-startup-error":
      case "notebook-document-transaction":
        return;

      case "completed-run":
        store.set(islandsPendingInitialRunsAtom, (pending) => {
          if (!pending?.has(sessionGeneration)) {
            return pending;
          }
          const next = new Set(pending);
          next.delete(sessionGeneration);
          return next;
        });
        return;

      case "kernel-ready":
        handleKernelReady(msg, {
          autoInstantiate: true,
          setCells: Functions.NOOP,
          setLayoutData: Functions.NOOP,
          setAppConfig: Functions.NOOP,
          setCapabilities: Functions.NOOP,
          setKernelState: Functions.NOOP,
          onError: Logger.error,
        });
        if (!window.customElements?.get(ISLAND_TAG_NAMES.ISLAND)) {
          defineCustomElement(ISLAND_TAG_NAMES.ISLAND, MarimoIslandElement);
        }
        return;

      case "send-ui-element-message":
        UI_ELEMENT_REGISTRY.broadcastMessage(
          msg.ui_element,
          msg.message,
          safeExtractSetUIElementMessageBuffers(msg),
        );
        return;

      case "remove-ui-elements":
        handleRemoveUIElements(msg);
        return;

      case "function-call-result":
        FUNCTIONS_REGISTRY.resolve(msg.function_call_id, msg);
        return;

      case "cell-op":
        handleCellNotificationeration(msg, actions.handleCellMessage);
        return;

      case "alert":
        toast({
          title: msg.title,
          description: renderHTML({ html: msg.description }),
          variant: msg.variant,
        });
        return;

      case "query-params-append":
        queryParamHandlers.append(msg);
        return;
      case "query-params-set":
        queryParamHandlers.set(msg);
        return;
      case "query-params-delete":
        queryParamHandlers.delete(msg);
        return;
      case "query-params-clear":
        queryParamHandlers.clear();
        return;

      case "model-lifecycle":
        handleWidgetMessage(WIDGET_REGISTRY, msg);
        return;

      case "consumer-capabilities":
      case "execution":
        return;
      default:
        logNever(msg);
        return;
    }
  } catch (error) {
    Logger.error("Failed to handle kernel message:", error);
  }
}
