/* Copyright 2024 Marimo. All rights reserved. */
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
    const target = e.target as HTMLElement;
    return (
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName.startsWith("MARIMO") ||
      Events.fromCodeMirror(e)
    );
  },

  /**
   * Returns true if the event is coming from a code editor.
   */
  fromCodeMirror: (e: Pick<KeyboardEvent, "target">) => {
    const target = e.target as HTMLElement;
    return target.closest(".cm-editor") !== null;
  },

  /**
   * Returns true if the event should be ignored because it's coming from a
   * form element or code editor.
   */
  shouldIgnoreKeyboardEvent(e: KeyboardEvent) {
    // Check for common form elements where keyboard shortcuts should be ignored
    return (
      e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement ||
      e.target instanceof HTMLSelectElement ||
      (e.target instanceof HTMLElement &&
        (e.target.isContentEditable ||
          e.target.tagName === "BUTTON" ||
          e.target.closest("[role='textbox']") !== null ||
          e.target.closest("[contenteditable='true']") !== null ||
          e.target.closest(".cm-editor") !== null)) // Add check for CodeMirror editor
    );
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
