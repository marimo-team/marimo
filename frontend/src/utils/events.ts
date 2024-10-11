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
};
