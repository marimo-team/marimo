/* Copyright 2024 Marimo. All rights reserved. */
import "./islands.css";
import "iconify-icon";

import { initializePlugins } from "@/plugins/plugins";
import { IslandsPyodideBridge } from "./bridge";
import { store } from "../state/jotai";
import {
  createNotebookActions,
  notebookAtom,
  notebookReducer,
} from "../cells/cells";
import { toast } from "@/components/ui/use-toast";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { logNever } from "@/utils/assertNever";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import {
  handleKernelReady,
  handleRemoveUIElements,
  handleCellOperation,
} from "../kernel/handlers";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import { Logger } from "@/utils/Logger";
import { Functions } from "@/utils/functions";
import { defineCustomElement } from "../dom/defineCustomElement";
import { MarimoIslandElement } from "./components/web-components";
import { RuntimeState } from "../kernel/RuntimeState";
import { sendComponentValues } from "../network/requests";
import type { RequestId } from "../network/DeferredRequestRegistry";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import type { UIElementId } from "../cells/ids";
import { MarimoValueInputEvent } from "../dom/events";
import {
  shouldShowIslandsWarningIndicatorAtom,
  userTriedToInteractWithIslandsAtom,
} from "./state";
import { dismissIslandsLoadingToast, toastIslandsLoading } from "./toast";
import type { Base64String } from "@/utils/json/base64";

/**
 * Main entry point for the js bundle for embedded marimo apps.
 */

/**
 * Initialize the Marimo app.
 */
export async function initialize() {
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
    switch (msg.op) {
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
      case "secret-keys-result":
        // Unsupported
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
          msg.data.buffers as Base64String[],
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
      default:
        logNever(msg);
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
  RuntimeState.INSTANCE.start(sendComponentValues);
}

initialize();
