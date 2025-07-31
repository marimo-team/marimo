/* Copyright 2024 Marimo. All rights reserved. */

export function handleDragging(isDragging: boolean) {
  if (!isDragging) {
    // Once the user is done dragging, dispatch a resize event
    window.dispatchEvent(new Event("resize"));
  }
}
