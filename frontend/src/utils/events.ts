/* Copyright 2026 Marimo. All rights reserved. */
export const Events = {
  stopPropagation: <
    E extends Pick<Event, "stopPropagation" | "preventDefault">,
  >(
    callback?: (evt: E) => void,
  ) => {
    return (event: E) => {
      event.stopPropagation();
      if (callback) {
        callback(event);
      }
    };
  },
  onEnter: <E extends Pick<KeyboardEvent, "key">>(
    callback?: (evt: E) => void,
  ) => {
    return (event: E) => {
      if (event.key === "Enter" && callback) {
        callback(event);
      }
    };
  },
  /**
   * This is used when we are focused in a code-editor,
   * but don't want pressing a button to move focus to that
   * button and instead stay in the code editor.
   *
   * This should only be placed on the onMouseDown callback
   */
  preventFocus: (e: React.MouseEvent) => {
    // Prevent focus moving to the button on click
    e.preventDefault();
  },

  /**
   * Returns true if the event is coming from a text input
   */
  fromInput: (e: Pick<KeyboardEvent, "target">) => {
    const target = Events.composedTarget(e);
    return (
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName.startsWith("MARIMO") ||
      target.isContentEditable ||
      Events.fromCodeMirror(target)
    );
  },

  /**
   * Returns true if the event is coming from a code editor.
   */
  fromCodeMirror: (target: HTMLElement) => {
    return target.closest(".cm-editor") !== null;
  },

  /**
   * Returns true if the event should be ignored because it's coming from a
   * form element or code editor.
   */
  shouldIgnoreKeyboardEvent(e: KeyboardEvent) {
    const target = Events.composedTarget(e);
    return (
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement ||
      (target instanceof HTMLElement &&
        (target.isContentEditable ||
          target.tagName === "BUTTON" ||
          target.closest("[role='textbox']") !== null ||
          target.closest("[contenteditable='true']") !== null ||
          Events.fromCodeMirror(target)))
    );
  },

  /**
   * Resolve the real event target, piercing shadow DOM retargeting.
   * Falls back to e.target for synthetic events (e.g. React Aria)
   * that don't expose composedPath.
   *
   * Without this, e.target is the shadow host (e.g. <marimo-text>) rather than the
   * real <input> inside it, so instanceof checks fail. (#4230)
   */
  composedTarget(e: Pick<Event, "target">): HTMLElement {
    if ("composedPath" in e && typeof e.composedPath === "function") {
      return (e.composedPath()[0] ?? e.target) as HTMLElement;
    }
    return e.target as HTMLElement;
  },

  hasModifier: (
    e: Pick<KeyboardEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey">,
  ) => {
    return e.ctrlKey || e.metaKey || e.altKey || e.shiftKey;
  },

  isMetaOrCtrl: (e: Pick<KeyboardEvent, "metaKey" | "ctrlKey">) => {
    return e.metaKey || e.ctrlKey;
  },
};
