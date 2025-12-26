/* Copyright 2026 Marimo. All rights reserved. */
import type { UIElementId } from "../cells/ids";

export function defineCustomEvent<T extends string>(eventName: T) {
  return <D>() => ({
    TYPE: eventName,
    is(event: Event): event is CustomEvent<D> {
      return event.type === eventName;
    },
    create(init: CustomEventInit<D>) {
      return new CustomEvent(eventName, init);
    },
  });
}

export type ValueType = unknown;

export const MarimoValueInputEvent = defineCustomEvent("marimo-value-input")<{
  value: ValueType;
  element: HTMLElement;
}>();
export type MarimoValueInputEventType = ReturnType<
  typeof MarimoValueInputEvent.create
>;

export const MarimoValueUpdateEvent = defineCustomEvent("marimo-value-update")<{
  value: ValueType;
  element: HTMLElement;
}>();
export type MarimoValueUpdateEventType = ReturnType<
  typeof MarimoValueUpdateEvent.create
>;

export const MarimoValueReadyEvent = defineCustomEvent("marimo-value-ready")<{
  objectId: UIElementId;
}>();
export type MarimoValueReadyEventType = ReturnType<
  typeof MarimoValueReadyEvent.create
>;

export const MarimoIncomingMessageEvent = defineCustomEvent(
  "marimo-incoming-message",
)<{
  objectId: UIElementId;
  message: unknown;
  buffers: readonly DataView[];
}>();
export type MarimoIncomingMessageEventType = ReturnType<
  typeof MarimoIncomingMessageEvent.create
>;

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
  return MarimoValueInputEvent.create({
    bubbles: true, // bubble to tell marimo that a value has changed
    composed: true,
    detail: { value: value, element: element },
  });
}

// Augment the global namespace to include the custom events
declare global {
  interface HTMLElementEventMap {
    [MarimoValueInputEvent.TYPE]: MarimoValueInputEventType;
    [MarimoValueUpdateEvent.TYPE]: MarimoValueUpdateEventType;
    [MarimoValueReadyEvent.TYPE]: MarimoValueReadyEventType;
    [MarimoIncomingMessageEvent.TYPE]: MarimoIncomingMessageEventType;
  }

  interface DocumentEventMap {
    [MarimoValueInputEvent.TYPE]: MarimoValueInputEventType;
    [MarimoValueUpdateEvent.TYPE]: MarimoValueUpdateEventType;
    [MarimoValueReadyEvent.TYPE]: MarimoValueReadyEventType;
    [MarimoIncomingMessageEvent.TYPE]: MarimoIncomingMessageEventType;
  }
}
