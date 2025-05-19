/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "@/utils/Logger";
import type { CellId, UIElementId } from "../cells/ids";
import {
  type ValueType,
  MarimoIncomingMessageEvent,
  MarimoValueReadyEvent,
  MarimoValueUpdateEvent,
} from "./events";
import { parseInitialValue } from "./htmlUtils";
import { byteStringToDataView } from "@/utils/data-views";
import type { Base64String } from "@/utils/json/base64";
import { typedAtob } from "@/utils/json/base64";

interface UIElementEntry {
  objectId: string;
  value: ValueType;
  // elements synchronized by a UIElement (in the DOM, each
  // <marimo-ui-element>'s first child)
  elements: Set<HTMLElement>;
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
  // maps UIElement objectIds to entries.
  entries: Map<string, UIElementEntry>;

  /**
   * Shared instance of UIElementRegistry since this must be a singleton.
   */
  static get INSTANCE(): UIElementRegistry {
    const KEY = "_marimo_private_UIElementRegistry";
    if (!window[KEY]) {
      window[KEY] = new UIElementRegistry();
    }
    return window[KEY] as UIElementRegistry;
  }

  private constructor() {
    this.entries = new Map();
  }

  has(objectId: UIElementId): boolean {
    return this.entries.has(objectId);
  }

  set(objectId: UIElementId, value: ValueType): void {
    if (this.entries.has(objectId)) {
      throw new Error(`UIElement ${objectId} already registered`);
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
  registerInstance(objectId: UIElementId, instance: HTMLElement) {
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
  removeInstance(objectId: UIElementId, instance: HTMLElement) {
    const entry = this.entries.get(objectId);
    // The UIElement can be removed from the registry before all
    // instances are removed: UIElement removal is triggered
    // when the tied Python object goes out of scope, but instance
    // removal is triggered when the instance is removed from the DOM
    // (which can happen after Python deconstruction)
    if (entry?.elements.has(instance)) {
      entry.elements.delete(instance);
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
  removeElementsByCell(cellId: CellId) {
    const objectIds = [...this.entries.keys()].filter((objectId) =>
      objectId.startsWith(`${cellId}-`),
    );

    objectIds.forEach((objectId) => {
      this.entries.delete(objectId);
    });
  }

  /**
   * Get the value of a registered UIElement.
   *
   * @param objectId - id of the UIElement
   * @returns the value for `objectId`, or `undefined` if the object was not found.
   */
  lookupValue(objectId: string): ValueType {
    const entry = this.entries.get(objectId);
    return entry === undefined ? undefined : entry.value;
  }

  broadcastMessage(
    objectId: UIElementId,
    message: unknown,
    buffers: Base64String[] | undefined | null,
  ): void {
    const entry = this.entries.get(objectId);
    if (entry === undefined) {
      Logger.warn("UIElementRegistry missing entry", objectId);
    } else {
      const toDataView = (base64: Base64String) => {
        return byteStringToDataView(typedAtob(base64));
      };
      entry.elements.forEach((element) => {
        element.dispatchEvent(
          MarimoIncomingMessageEvent.create({
            bubbles: false, // only the intended target gets the message
            composed: true,
            detail: {
              objectId: objectId,
              message: message,
              buffers: buffers ? buffers.map(toDataView) : undefined,
            },
          }),
        );
      });
    }
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
  broadcastValueUpdate(
    initiator: HTMLElement,
    objectId: UIElementId,
    value: ValueType,
  ): void {
    const entry = this.entries.get(objectId);
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
