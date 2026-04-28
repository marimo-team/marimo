/* Copyright 2026 Marimo. All rights reserved. */

import { toast } from "@/components/ui/use-toast";
import { ISLAND_CSS_CLASSES, ISLAND_TAG_NAMES } from "@/core/islands/constants";
import { renderHTML } from "@/plugins/core/RenderHTML";
import {
  handleWidgetMessage,
  MODEL_MANAGER,
} from "@/plugins/impl/anywidget/model";
import { initializePlugins } from "@/plugins/plugins";
import { Functions } from "@/utils/functions";
import {
  safeExtractSetUIElementMessageBuffers,
  type JsonString,
} from "@/utils/json/base64";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { Logger } from "@/utils/Logger";
import { logNever } from "@/utils/assertNever";
import {
  createNotebookActions,
  notebookAtom,
  notebookReducer,
} from "../cells/cells";
import { defineCustomElement } from "../dom/defineCustomElement";
import { MarimoValueInputEvent } from "../dom/events";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import {
  handleCellNotificationeration,
  handleKernelReady,
  handleRemoveUIElements,
} from "../kernel/handlers";
import type {
  NotificationMessage,
  NotificationMessageType,
} from "../kernel/messages";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import { RuntimeState } from "../kernel/RuntimeState";
import { initialModeAtom } from "../mode";
import { requestClientAtom } from "../network/requests";
import { store as defaultStore } from "../state/jotai";
import type { IslandsPyodideBridge } from "./bridge";
import { MarimoIslandElement } from "./components/web-components";
import {
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
    if (showing) {
      toastIslandsLoading();
      for (const island of islands) {
        island.style.setProperty("opacity", "0.5");
      }
    } else {
      dismissIslandsLoadingToast();
      for (const island of islands) {
        island.style.removeProperty("opacity");
      }
    }
  });

  // Wire up kernel message handling
  // The wire format is {"op": "...", "data": {"op": "...", ...}} — both
  // the envelope and the payload carry the op. The bridge types the message
  // as NotificationPayload (just {data}), but the actual wire format
  // includes the outer op too.
  bridge.consumeMessages((message) => {
    handleMessage(
      message as unknown as JsonString<IslandsNotificationMessage>,
      actions,
    );
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

type IslandsNotificationMessage = {
  [K in NotificationMessageType]: {
    data: Extract<NotificationMessage, { op: K }>;
    op: K;
  };
}[NotificationMessageType];

/**
 * Handles a single message from the kernel.
 *
 * Wire format from Python: {"op": "<name>", "data": {"op": "<name>", ...}}
 */
function handleMessage(
  message: JsonString<IslandsNotificationMessage>,
  actions: NotebookActions,
): void {
  try {
    const msg = jsonParseWithSpecialChar(message);
    Logger.debug("Islands received message:", msg.op);

    switch (msg.op) {
      // Unsupported operations in islands mode
      case "banner":
      case "missing-package-alert":
      case "installing-package-alert":
      case "completion-result":
      case "reload":
      case "focus-cell":
      case "variables":
      case "variable-values":
      case "data-column-preview":
      case "sql-table-preview":
      case "sql-table-list-preview":
      case "sql-schema-list-preview":
      case "datasets":
      case "data-source-connections":
      case "validate-sql-result":
      case "storage-namespaces":
      case "storage-entries":
      case "storage-download-ready":
      case "secret-keys-result":
      case "startup-logs":
      case "completed-run":
      case "interrupted":
      case "reconnected":
      case "cache-cleared":
      case "cache-info":
      case "kernel-startup-error":
      case "notebook-document-transaction":
      case "build-event":
        return;

      case "kernel-ready":
        handleKernelReady(msg.data, {
          autoInstantiate: true,
          setCells: actions.setCells,
          setLayoutData: Functions.NOOP,
          setAppConfig: Functions.NOOP,
          setCapabilities: Functions.NOOP,
          setKernelState: Functions.NOOP,
          onError: Logger.error,
        });
        defineCustomElement(ISLAND_TAG_NAMES.ISLAND, MarimoIslandElement);
        return;

      case "send-ui-element-message":
        UI_ELEMENT_REGISTRY.broadcastMessage(
          msg.data.ui_element,
          msg.data.message,
          safeExtractSetUIElementMessageBuffers(msg.data),
        );
        return;

      case "remove-ui-elements":
        handleRemoveUIElements(msg.data);
        return;

      case "function-call-result":
        FUNCTIONS_REGISTRY.resolve(msg.data.function_call_id, msg.data);
        return;

      case "cell-op":
        handleCellNotificationeration(msg.data, actions.handleCellMessage);
        return;

      case "alert":
        toast({
          title: msg.data.title,
          description: renderHTML({ html: msg.data.description }),
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

      case "model-lifecycle":
        handleWidgetMessage(MODEL_MANAGER, msg.data);
        return;

      default:
        logNever(msg);
        return;
    }
  } catch (error) {
    Logger.error("Failed to handle kernel message:", error);
  }
}
