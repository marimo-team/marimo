/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import type { CellId, UIElementId } from "../cells/ids";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import type { FunctionRequest } from "../functions/host-function";
import {
  MarimoIncomingMessageEvent,
  MarimoValueReadyEvent,
  MarimoValueUpdateEvent,
  type ValueType,
} from "./events";
import { parseInitialValue } from "./htmlUtils";

/**
 * Kernel-initiated UI value update, sent via the existing
 * `send-ui-element-message` channel when `set_ui_value` (code_mode)
 * changes a widget's value so the frontend can reflect the new state.
 */
interface UIValueUpdateMessage {
  type: "marimo-ui-value-update";
  value: ValueType;
}

function isUIValueUpdateMessage(msg: unknown): msg is UIValueUpdateMessage {
  if (typeof msg !== "object" || msg === null) {
    return false;
  }
  return "type" in msg && msg.type === "marimo-ui-value-update";
}

interface UIElementEntry {
  objectId: string;
  value: ValueType;
  // elements synchronized by a UIElement (in the DOM, each
  // <marimo-ui-element>'s first child)
  elements: Set<HTMLElement>;
  hostManaged?: boolean;
}

export interface UIElementStateSource {
  values(): ReadonlyMap<string, unknown>;
  subscribe(listener: () => void): () => void;
  update(id: string, value: unknown): Promise<void>;
}

/* UIElementRegistry
 *
 * Maintains state for each UI element that is rendered in the
 * DOM (including shadow DOMs), and handles dispatching of events
 * to UI elements when values are updated.
 *
 * Expects object IDs to have the form <cellId>-<suffixId>
 */
export class UIElementRegistry {
  private functionSource:
    | ((id: string) => FunctionRequest | undefined)
    | undefined;

  public connectFunctions(source: (id: string) => FunctionRequest | undefined) {
    this.functionSource = source;
    return () => {
      if (this.functionSource === source) {
        this.functionSource = undefined;
      }
    };
  }

  public functionRequest(id: string | null): FunctionRequest {
    return (
      (id === null ? undefined : this.functionSource?.(id)) ??
      ((request) => FUNCTIONS_REGISTRY.request(request))
    );
  }

  private source: UIElementStateSource | undefined;
  // maps UIElement objectIds to entries.
  public entries: Map<UIElementId, UIElementEntry>;

  /**
   * Shared instance of UIElementRegistry since this must be a singleton.
   */
  public static get INSTANCE(): UIElementRegistry {
    const KEY = "_marimo_private_UIElementRegistry";
    if (!window[KEY]) {
      window[KEY] = new UIElementRegistry();
    }
    return window[KEY] as UIElementRegistry;
  }

  private constructor() {
    this.entries = new Map();
  }

  /** Connect confirmed values and local drafts without depending on their store. */
  public connectHost(source: UIElementStateSource): () => void {
    this.source = source;
    const refresh = () => {
      if (this.source !== source) {
        return;
      }
      const values = source.values();
      for (const [id, entry] of this.entries) {
        if (entry.hostManaged && !values.has(id)) {
          entry.value = undefined;
          if (entry.elements.size === 0) {
            this.entries.delete(id);
          }
        }
      }
      for (const [id, value] of values) {
        // The host and HTML wrapper use the same Python UIElement identity.
        const objectId = id as UIElementId;
        let entry = this.entries.get(objectId);
        if (!entry) {
          this.set(objectId, value);
          entry = this.entries.get(objectId);
        }
        if (entry) {
          entry.hostManaged = true;
          this.applyValue(entry, value);
        }
      }
    };
    const unsubscribe = source.subscribe(refresh);
    refresh();
    return () => {
      unsubscribe();
      if (this.source === source) {
        this.source = undefined;
        for (const [id, entry] of this.entries) {
          if (entry.hostManaged) {
            this.entries.delete(id);
          }
        }
      }
    };
  }

  private applyValue(entry: UIElementEntry, value: unknown): void {
    if (Object.is(entry.value, value)) {
      return;
    }
    entry.value = value;
    for (const element of entry.elements) {
      element.dispatchEvent(
        MarimoValueUpdateEvent.create({
          bubbles: false,
          composed: true,
          detail: { value, element },
        }),
      );
    }
  }

  public has(objectId: UIElementId): boolean {
    return this.entries.has(objectId);
  }

  public set(objectId: UIElementId, value: ValueType): void {
    // Legacy resume values must not replace host state or pending input.
    if (this.entries.get(objectId)?.hostManaged) {
      return;
    }
    if (this.entries.has(objectId)) {
      Logger.debug(
        "UIElementRegistry overwriting entry for objectId.",
        objectId,
      );
    }
    this.entries.set(objectId, {
      objectId: objectId,
      value: value,
      elements: new Set(),
    });
  }

  /**
   * Register an instance of a UIElement
   *
   * @param objectId - id of the UIElement
   * @param instance - the HTMLElement that the UIElement wraps
   */
  public registerInstance(objectId: UIElementId, instance: HTMLElement) {
    const entry = this.entries.get(objectId);
    if (entry === undefined) {
      this.entries.set(objectId, {
        objectId: objectId,
        value: parseInitialValue(instance, this),
        elements: new Set([instance]),
      });
    } else {
      entry.elements.add(instance);
    }
  }

  /**
   * Remove an instance of a UIElement
   *
   * @remarks
   * Should be called when a UIElement node is removed from the DOM.
   *
   * @param objectId - id of the UIElement
   * @param instance - the HTMLElement to remove
   *
   */
  public removeInstance(objectId: UIElementId, instance: HTMLElement) {
    const entry = this.entries.get(objectId);
    // The UIElement can be removed from the registry before all
    // instances are removed: UIElement removal is triggered
    // when the tied Python object goes out of scope, but instance
    // removal is triggered when the instance is removed from the DOM
    // (which can happen after Python deconstruction)
    if (entry?.elements.has(instance)) {
      entry.elements.delete(instance);
      if (
        entry.hostManaged &&
        entry.elements.size === 0 &&
        !this.source?.values().has(objectId)
      ) {
        this.entries.delete(objectId);
      }
    }
  }

  /**
   * Remove all UIElements associated with a particular cell from the registry.
   *
   * Doesn't destroy or unmount HTML elements, just removes associated state
   * from the registry.
   *
   * @param cellId - stringified cellId
   */
  public removeElementsByCell(cellId: CellId) {
    const objectIds = [...this.entries.keys()].filter((objectId) =>
      objectId.startsWith(`${cellId}-`),
    );

    objectIds.forEach((objectId) => {
      if (!this.entries.get(objectId)?.hostManaged) {
        this.entries.delete(objectId);
      }
    });
  }

  /**
   * Get the value of a registered UIElement.
   *
   * @param objectId - id of the UIElement
   * @returns the value for `objectId`, or `undefined` if the object was not found.
   */
  public lookupValue(objectId: UIElementId): ValueType {
    const entry = this.entries.get(objectId);
    return entry === undefined ? undefined : entry.value;
  }

  public broadcastMessage(
    objectId: UIElementId,
    message: unknown,
    buffers: readonly DataView[],
  ): void {
    const entry = this.entries.get(objectId);
    if (entry === undefined) {
      Logger.warn("UIElementRegistry missing entry", objectId);
      return;
    }

    // Kernel-initiated value update — push into DOM elements without
    // dispatching MarimoValueReadyEvent to avoid a round-trip.
    if (isUIValueUpdateMessage(message)) {
      if (entry.hostManaged) {
        return;
      }
      entry.value = message.value;
      entry.elements.forEach((element) => {
        element.dispatchEvent(
          MarimoValueUpdateEvent.create({
            bubbles: false,
            composed: true,
            detail: { value: message.value, element: element },
          }),
        );
      });
      return;
    }

    entry.elements.forEach((element) => {
      element.dispatchEvent(
        MarimoIncomingMessageEvent.create({
          bubbles: false, // only the intended target gets the message
          composed: true,
          detail: {
            objectId: objectId,
            message: message,
            buffers: buffers,
          },
        }),
      );
    });
  }

  /**
   * Broadcast `value` to instances of the component with id `objectId`
   *
   * Additionally, sends a message to alert the app that an object has a new
   * value that should be sent to the kernel.
   *
   * @param initiator - child element that initiated the broadcast
   * @param objectId - id of the UIElement
   * @param value - value to broadcast
   */
  public broadcastValueUpdate(
    initiator: HTMLElement,
    objectId: UIElementId,
    value: ValueType,
  ): void {
    const entry = this.entries.get(objectId);
    if (entry?.hostManaged && this.source) {
      const source = this.source;
      void source.update(objectId, value).catch((error: unknown) => {
        Logger.warn("UI element update failed", error);
        if (this.source === source && source.values().has(objectId)) {
          initiator.dispatchEvent(
            MarimoValueUpdateEvent.create({
              bubbles: false,
              composed: true,
              detail: {
                value: source.values().get(objectId),
                element: initiator,
              },
            }),
          );
        }
      });
      return;
    }
    if (entry === undefined) {
      Logger.warn("UIElementRegistry missing entry", objectId);
    } else {
      entry.value = value;
      entry.elements.forEach((element) => {
        if (element !== initiator) {
          element.dispatchEvent(
            MarimoValueUpdateEvent.create({
              bubbles: false, // only the intended target gets the message
              composed: true,
              detail: { value: value, element: element },
            }),
          );
        }
      });

      document.dispatchEvent(
        MarimoValueReadyEvent.create({
          bubbles: true,
          composed: true,
          detail: {
            objectId: objectId,
          },
        }),
      );
    }
  }
}

export const UI_ELEMENT_REGISTRY = UIElementRegistry.INSTANCE;
