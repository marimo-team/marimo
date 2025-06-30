/* Copyright 2024 Marimo. All rights reserved. */

export function handleDragging(isDragging: boolean) {
  if (!isDragging) {
    // Once the user is done dragging, dispatch a resize event
    globalThis.dispatchEvent(new Event("resize"));
  }
}
