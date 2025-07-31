/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import {
  MarimoValueReadyEvent,
  type MarimoValueReadyEventType,
} from "../dom/events";
import { UI_ELEMENT_REGISTRY, type UIElementRegistry } from "../dom/uiregistry";
import type { RunRequests } from "../network/types";

/**
 * Manager to track running cells.
 */
export class RuntimeState {
  private hasStarted = false;

  /**
   * Shared instance of RuntimeState since this must be a singleton.
   */
  static get INSTANCE(): RuntimeState {
    const KEY = "_marimo_private_RuntimeState";
    if (!window[KEY]) {
      window[KEY] = new RuntimeState(UI_ELEMENT_REGISTRY);
    }
    return window[KEY] as RuntimeState;
  }

  /**
   * ObjectIds of UIElements whose values need to be updated in the kernel
   */
  private _sendComponentValues: RunRequests["sendComponentValues"] | undefined;

  constructor(private uiElementRegistry: UIElementRegistry) {}

  private get sendComponentValues(): RunRequests["sendComponentValues"] {
    if (!this._sendComponentValues) {
      throw new Error("sendComponentValues is not set");
    }
    return this._sendComponentValues;
  }

  /**
   * Start listening for events from UIElements
   */
  start(sendComponentValues: RunRequests["sendComponentValues"]) {
    if (this.hasStarted) {
      Logger.warn("RuntimeState already started");
      return;
    }
    this._sendComponentValues = sendComponentValues;
    document.addEventListener(
      MarimoValueReadyEvent.TYPE,
      this.handleReadyEvent,
    );
    this.hasStarted = true;
  }

  /**
   * Stop listening for events from UIElements
   */
  stop() {
    if (!this.hasStarted) {
      Logger.warn("RuntimeState already stopped");
      return;
    }
    document.removeEventListener(
      MarimoValueReadyEvent.TYPE,
      this.handleReadyEvent,
    );
    this.hasStarted = false;
  }

  private handleReadyEvent = (e: MarimoValueReadyEventType) => {
    const objectId = e.detail.objectId;
    if (!this.uiElementRegistry.has(objectId)) {
      return;
    }

    const value = this.uiElementRegistry.lookupValue(objectId);
    if (value !== undefined) {
      this.sendComponentValues({
        objectIds: [objectId],
        values: [value],
      }).catch(
        // This happens if the run failed to register (401, 403, network
        // error, etc.) A run may fail if the kernel is restarted or the
        // notebook is closed.
        (error) => {
          Logger.warn(error);
        },
      );
    }
  };
}
