/* Copyright 2024 Marimo. All rights reserved. */
import { UIElementId } from "../cells/ids";

export type ValueType = unknown;

export type MarimoValueInputEventType = CustomEvent<{
  value: ValueType;
  element: HTMLElement;
}>;
export const marimoValueInputEvent = "marimo-value-input";

export type MarimoValueUpdateEventType = CustomEvent<{
  value: ValueType;
  element: HTMLElement;
}>;
export const marimoValueUpdateEvent = "marimo-value-update";

export type MarimoValueReadyEventType = CustomEvent<{ objectId: UIElementId }>;
export const marimoValueReadyEvent = "marimo-value-ready";

/**
 * Create a custom event to communicate a change in value
 *
 * This function should be used by UI elements to tell marimo that
 * their value has changed.
 *
 * We also pass in the UI element that is triggering the change.
 * We cannot simply use `e.target` because of "Event Retargeting"
 * which is a feature of the Shadow DOM, that ensures encapsulation by
 * re-targeting events that are emitted from within a shadow root to
 * the shadow root's host element. We do not want to re-target the event
 * because we want to know which element triggered the event.
 *
 * @param value - the new value of the component
 * @param element - the element that changed
 */
export function createInputEvent(
  value: ValueType,
  element: HTMLElement,
): MarimoValueInputEventType {
  return new CustomEvent(marimoValueInputEvent, {
    bubbles: true, // bubble to tell marimo that a value has changed
    composed: true,
    detail: { value: value, element: element },
  });
}

// Augment the global namespace to include the custom events
declare global {
  interface HTMLElementEventMap {
    "marimo-value-input": MarimoValueInputEventType;
    "marimo-value-update": MarimoValueUpdateEventType;
    "marimo-value-ready": MarimoValueReadyEventType;
  }

  interface DocumentEventMap {
    "marimo-value-input": MarimoValueInputEventType;
    "marimo-value-update": MarimoValueUpdateEventType;
    "marimo-value-ready": MarimoValueReadyEventType;
  }
}
