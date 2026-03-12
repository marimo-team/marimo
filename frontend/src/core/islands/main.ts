/* Copyright 2026 Marimo. All rights reserved. */
import "./islands.css";
import "../../css/common.css";
import "../../css/globals.css";
import "../../css/codehilite.css";
import "../../css/katex.min.css";
import "../../css/md.css";
import "../../css/admonition.css";
import "../../css/md-tooltip.css";
import "../../css/table.css";

import "iconify-icon";

import { toast } from "@/components/ui/use-toast";
import { renderHTML } from "@/plugins/core/RenderHTML";
import {
  handleWidgetMessage,
  MODEL_MANAGER,
} from "@/plugins/impl/anywidget/model";
import { initializePlugins } from "@/plugins/plugins";
import { logNever } from "@/utils/assertNever";
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
  handleCellNotificationeration,
  handleKernelReady,
  handleRemoveUIElements,
} from "../kernel/handlers";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import { RuntimeState } from "../kernel/RuntimeState";
import { initialModeAtom } from "../mode";
import type { RequestId } from "../network/DeferredRequestRegistry";
import { requestClientAtom } from "../network/requests";
import { store } from "../state/jotai";
import { IslandsPyodideBridge } from "./bridge";
import { MarimoIslandElement } from "./components/web-components";
import {
  shouldShowIslandsWarningIndicatorAtom,
  userTriedToInteractWithIslandsAtom,
} from "./state";
import { dismissIslandsLoadingToast, toastIslandsLoading } from "./toast";

/**
 * Main entry point for the js bundle for embedded marimo apps.
 */

/**
 * Initialize the Marimo app.
 */
export async function initialize() {
  // Setup networking
  store.set(requestClientAtom, IslandsPyodideBridge.INSTANCE);
  store.set(initialModeAtom, "read");

  // This will display all the static HTML content.
  initializePlugins();

  // Find all `marimo-island` elements.
  const islands = document.querySelectorAll<HTMLElement>(
    MarimoIslandElement.tagName,
  );

  // If no islands are found, we can skip the rest of the initialization.
  if (islands.length === 0) {
    return;
  }

  // Add 'marimo' class name to all `marimo-island` elements.
  // This makes our styles apply to the islands.
  for (const island of islands) {
    island.classList.add(MarimoIslandElement.styleNamespace);
  }

  const actions = createNotebookActions((action) => {
    store.set(notebookAtom, (state) => notebookReducer(state, action));
  });

  // If the user has interacted with the islands before they are initialized,
  // we show the loading toast.
  store.sub(shouldShowIslandsWarningIndicatorAtom, () => {
    const showing = store.get(shouldShowIslandsWarningIndicatorAtom);
    if (showing) {
      toastIslandsLoading();
      // For each island, set the opacity to 0.5
      for (const island of islands) {
        island.style.setProperty("opacity", "0.5");
      }
    } else {
      dismissIslandsLoadingToast();
      // For each island, remove the opacity
      for (const island of islands) {
        island.style.removeProperty("opacity");
      }
    }
  });

  // Consume messages from the kernel
  IslandsPyodideBridge.INSTANCE.consumeMessages((message) => {
    const msg = jsonParseWithSpecialChar(message);
    switch (msg.data.op) {
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
      case "storage-namespaces":
      case "storage-entries":
      case "storage-download-ready":
      case "secret-keys-result":
      case "startup-logs":
        // Unsupported
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
        // Define the custom element for the marimo-island tag.
        // This comes after initializing since this reads from the store.
        defineCustomElement(MarimoIslandElement.tagName, MarimoIslandElement);
        return;
      case "completed-run":
        return;
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
        handleCellNotificationeration(msg.data, actions.handleCellMessage);
        return;
      case "alert":
        // TODO: support toast with islands
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
        return;
      case "cache-cleared":
        return;
      case "cache-info":
        return;
      case "kernel-startup-error":
        return;
      case "model-lifecycle":
        handleWidgetMessage(MODEL_MANAGER, msg.data);
        return;
      default:
        logNever(msg.data);
    }
  });

  // Set the user tried to interact with islands
  // before they are initialized.
  document.addEventListener(
    MarimoValueInputEvent.TYPE,
    () => {
      store.set(userTriedToInteractWithIslandsAtom, true);
    },
    {
      once: true,
    },
  );

  // Start the runtime
  RuntimeState.INSTANCE.start(
    IslandsPyodideBridge.INSTANCE.sendComponentValues,
  );
}

initialize();
