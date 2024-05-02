/* Copyright 2024 Marimo. All rights reserved. */
import { sendComponentValues } from "@/core/network/requests";
import {
  marimoValueReadyEvent,
  MarimoValueReadyEventType,
} from "../dom/events";
import { UI_ELEMENT_REGISTRY, UIElementRegistry } from "../dom/uiregistry";
import { isStaticNotebook } from "../static/static-state";
import { RunRequests } from "../network/types";
import { repl } from "@/utils/repl";

/**
 * Manager to track running cells.
 */
export class RuntimeState {
  /**
   * Shared instance of RuntimeState since this must be a singleton.
   */
  static readonly INSTANCE = new RuntimeState(UI_ELEMENT_REGISTRY, {
    sendComponentValues,
  });

  // TODO(akshayka): move the running-count state machine to the Python kernel;
  // keeping track of it in the frontend is very brittle. the kernel can simply
  // choose to drop queued update requests when newer ones arrive
  /**
   * number of cells that are currently running, to implement debouncing
   * and batching of update requests
   */
  private runningCount: number;
  /**
   * ObjectIds of UIElements whose values need to be updated in the kernel
   */
  private componentsToUpdate: Set<string>;

  constructor(
    private uiElementRegistry: UIElementRegistry,
    private opts: {
      sendComponentValues: RunRequests["sendComponentValues"];
    },
  ) {
    this.runningCount = 0;
    this.componentsToUpdate = new Set();
    repl(RuntimeState.INSTANCE, "RuntimeState");
  }

  /**
   * Start listening for events from UIElements
   */
  start() {
    document.addEventListener(marimoValueReadyEvent, this.handleReadyEvent);
  }

  /**
   * Stop listening for events from UIElements
   */
  stop() {
    document.removeEventListener(marimoValueReadyEvent, this.handleReadyEvent);
  }

  registerRunStart(): void {
    this.runningCount += 1;
  }

  registerRunEnd(): void {
    // Threshold runningCount to 0 for resiliency. Won't be needed once
    // we merge UI component updates in Python
    this.runningCount = Math.max(this.runningCount - 1, 0);
  }

  running(): boolean {
    return this.runningCount > 0 && !isStaticNotebook();
  }

  flushUpdates() {
    if (this.componentsToUpdate.size > 0) {
      // Start a run
      this.registerRunStart();

      // Store the components to update, in case the run fails to be sent
      const previousComponentsToUpdate = new Set(this.componentsToUpdate);

      this.opts
        .sendComponentValues(
          Array.from(this.componentsToUpdate.values(), (objectId) => ({
            objectId: objectId,
            value: this.uiElementRegistry.lookupValue(objectId),
          })).filter((update) => update.value !== undefined),
        )
        .catch(() => {
          // This happens if the run was failed to register (401, 403, network error, etc.)
          // If the run fails, restore the components to update and finish the run
          // A run may fail if the kernel is restarted or the notebook is closed,
          // but if we don't restore registerRunEnd() will never be able to flush updates.
          this.registerRunEnd();
          // Merge the previous components to update with the current ones
          previousComponentsToUpdate.forEach((objectId) =>
            this.componentsToUpdate.add(objectId),
          );
        });
      this.componentsToUpdate.clear();
    }
  }

  private handleReadyEvent = (e: MarimoValueReadyEventType) => {
    const objectId = e.detail.objectId;
    if (!this.uiElementRegistry.has(objectId)) {
      return;
    }

    this.componentsToUpdate.add(objectId);
    if (!this.running()) {
      this.flushUpdates();
    }
  };
}
