/* Copyright 2024 Marimo. All rights reserved. */
import { repl } from "../../utils/repl";
import { CellId, UIElementId } from "../cells/ids";
import {
  ValueType,
  marimoValueUpdateEvent,
  marimoValueReadyEvent,
} from "./events";
import { parseInitialValue } from "./htmlUtils";

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
  static readonly INSTANCE = new UIElementRegistry();

  private constructor() {
    repl(UIElementRegistry.INSTANCE, "UIElementRegistry");
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
        value: parseInitialValue(instance),
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
    if (entry !== undefined && entry.elements.has(instance)) {
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
    if (entry !== undefined) {
      entry.value = value;
      entry.elements.forEach((element) => {
        if (element !== initiator) {
          element.dispatchEvent(
            new CustomEvent(marimoValueUpdateEvent, {
              bubbles: false, // only the intended target gets the message
              composed: true,
              detail: { value: value, element: element },
            }),
          );
        }
      });

      document.dispatchEvent(
        new CustomEvent(marimoValueReadyEvent, {
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
