/* Copyright 2023 Marimo. All rights reserved. */
import { sendComponentValues } from "@/core/network/requests";
import { marimoValueReadyEvent, MarimoValueReadyEventType } from "./dom/events";
import { UI_ELEMENT_REGISTRY, UIElementRegistry } from "./dom/uiregistry";

/**
 * Manager to track running cells.
 */
export class RuntimeState {
  /**
   * Shared instance of RuntimeState since this must be a singleton.
   */
  static readonly INSTANCE = new RuntimeState(UI_ELEMENT_REGISTRY);

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

  private constructor(private uiElementRegistry: UIElementRegistry) {
    this.runningCount = 0;
    this.componentsToUpdate = new Set();
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
    this.runningCount -= 1;
  }

  running(): boolean {
    return this.runningCount > 0;
  }

  flushUpdates() {
    if (this.componentsToUpdate.size > 0) {
      this.registerRunStart();
      sendComponentValues(
        Array.from(this.componentsToUpdate.values(), (objectId) => ({
          objectId: objectId,
          value: this.uiElementRegistry.lookupValue(objectId),
        })).filter((update) => update.value !== undefined)
      );
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
