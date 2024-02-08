/* Copyright 2024 Marimo. All rights reserved. */
import { isCustomMarimoElement } from "@/plugins/core/registerReactComponent";
import { Logger } from "../../utils/Logger";
import { Functions } from "../../utils/functions";
import { UIElementId } from "../cells/ids";
import { defineCustomElement } from "./defineCustomElement";
import { MarimoValueInputEventType, marimoValueInputEvent } from "./events";
import { UI_ELEMENT_REGISTRY } from "./uiregistry";

const UI_ELEMENT_TAG_NAME = "MARIMO-UI-ELEMENT";

interface IUIElement extends HTMLElement {
  reset(): void;
}

/**
 * Lazily initialize the UIElement component.
 */
export function initializeUIElement() {
  /**
   * UIElement Web Component
   *
   * Synchronizes the value of its first child on page and with the kernel.
   *
   * @example
   * Example wrapping a custom web component:
   * ```
   * <marimo-ui-element object-id="...">
   *   <my-custom-component data-initial-value="..."/>
   * </marimo-ui-element>
   * ```
   *
   * @example
   * Example wrapping raw HTML:
   * ```
   * <marimo-ui-element object-id="...">
   *   <div data-initial-value="...">
   *      ...
   *   </div>
   * </marimo-ui-element>
   * ```
   *
   * @remarks
   * IDENTIFICATION
   * UIElements are uniquely identified by their objectId, in the following
   * sense: UIElements with the same objectId are synchronized to have the same
   * value. In other words, the set of UIElements on the page can be partitioned
   * into equivalence classes, where two elements are equivalent if they share
   * the same objectId.
   *
   * Every UIElement is registered with the global UIElementRegistry.
   *
   * SYNCHRONIZATION
   * Using a <marimo-ui-element> tag declares that its first child is a component
   * whose value should be synchronized. Synchronization happens on two levels:
   *   1. multiple instances of the same component are synchronized to have the
   *      same value
   *   2. a change in value on the page is sent to the kernel
   *
   * INITIAL VALUE
   * The first child of <marimo-ui-element> may optionally take a data attribute
   * called "initial-value" to influence its instantiation. Upon instantiation,
   * the UIElement component may set this attribute if it already has a value
   * for the objectId.
   *
   * COMMUNICATION
   * Communication between marimo and the child of a UIElement is facilitated
   * by two events:
   *   1. marimoValueInputEvent: the child publishes its value by dispatching
   *      a marimoValueInputEvent, with `detail` set to
   *      `{ value: <the new value> }`;
   *   2. marimoValueUpdateEvent: the UIElement node broadcasts a
   *      marimoValueUpdateEvent to every element registered under its
   *      objectId when a new value is available; the targets of these
   *      events (i.e., the child node of each UIElement in the equivalence
   *      class of the objectId) are responsible for listening to these
   *      events and updating their value internally.
   *
   */
  class UIElement extends HTMLElement implements IUIElement {
    private initialized = false;
    private inputListener: (e: MarimoValueInputEventType) => void =
      Functions.NOOP;

    // This needs to happen in connectedCallback because the element may not be
    // set at construction time
    private init() {
      if (this.initialized) {
        return;
      }

      const objectId = UIElementId.parseOrThrow(this);
      this.inputListener = (e: MarimoValueInputEventType) => {
        // TODO: just fill in the objectId and let the document handle
        // broadcast? that would still let other elements cancel the event
        // while also reducing the number of event listeners on the document
        if (objectId !== null && e.detail.element === this.firstElementChild) {
          UI_ELEMENT_REGISTRY.broadcastValueUpdate(
            child as HTMLElement,
            objectId,
            e.detail.value,
          );
        }
      };

      // A UIElement tracks the value of its first child.
      const child = this.firstElementChild;
      if (objectId === null) {
        Logger.error("[marimo-ui-element] missing object-id attribute");
        return;
      } else if (child === null) {
        Logger.error("[marimo-ui-element] has no child");
        return;
      } else if (!(child instanceof HTMLElement)) {
        Logger.error(
          "[marimo-ui-element] first child must be instance of HTMLElement",
        );
        return;
      }

      this.initialized = true;
    }

    connectedCallback() {
      this.init();

      if (this.initialized) {
        // It is critical that the element is registered in this method,
        // and not in the constructor, since it may be disconnected and
        // reconnected without being re-constructed
        const objectId = UIElementId.parseOrThrow(this);
        const child = this.firstElementChild as HTMLElement;
        UI_ELEMENT_REGISTRY.registerInstance(objectId, child);

        // Listen to marimo input events provided by the child element: these
        // events are signals to this UIElement that our value should change.
        document.addEventListener(marimoValueInputEvent, this.inputListener);
      }
    }

    disconnectedCallback() {
      if (this.initialized) {
        // Unregister everything
        document.removeEventListener(marimoValueInputEvent, this.inputListener);
        const objectId = UIElementId.parseOrThrow(this);
        UI_ELEMENT_REGISTRY.removeInstance(
          objectId,
          this.firstElementChild as HTMLElement,
        );
      }
    }

    /**
     * Reset the value of the child element to its initial value.
     */
    reset() {
      const child = this.firstElementChild;
      if (isCustomMarimoElement(child)) {
        child.reset();
      } else {
        Logger.error(
          "[marimo-ui-element] first child must have a reset method",
        );
      }
    }

    // We look for changes to the random-id attribute, which is effectively
    // used like a React key. If the random-id changes, we need to unmount and
    // remount its child.
    static get observedAttributes() {
      return ["random-id"];
    }

    attributeChangedCallback(
      name: string,
      oldValue: string | null,
      newValue: string | null,
    ) {
      if (this.initialized) {
        const hasChanged = oldValue !== newValue;
        if (name === "random-id" && hasChanged) {
          // deregister/clean-up this instance
          this.disconnectedCallback();
          // remove and re-add its child to force it to re-render; note that
          // this doesn't reconstruct the UI element, only its child
          const child = this.firstElementChild;
          if (isCustomMarimoElement(child)) {
            child.rerender();
          } else {
            Logger.error(
              "[marimo-ui-element] first child must have a rerender method",
            );
          }
          // register the element and reset its initial value
          this.initialized = false;
          this.connectedCallback();
        }
      }
    }
  }

  defineCustomElement(UI_ELEMENT_TAG_NAME.toLowerCase(), UIElement);
}

/**
 * Given a node, check if its parent or itself is a UIElement,
 * and return its objectId if so.
 */
export function getUIElementObjectId(target: HTMLElement): UIElementId | null {
  if (!target) {
    return null;
  }

  if (target.nodeName === UI_ELEMENT_TAG_NAME) {
    return UIElementId.parseOrThrow(target);
  }

  const node = target.parentElement;
  if (node?.nodeName === UI_ELEMENT_TAG_NAME) {
    return UIElementId.parseOrThrow(node);
  }

  return null;
}

export function isUIElement(target: HTMLElement): target is IUIElement {
  return target.tagName === UI_ELEMENT_TAG_NAME;
}
