/* Copyright 2026 Marimo. All rights reserved. */

import { raf2 } from "../../navigation/focus-utils";

export function handleDragging(isDragging: boolean) {
  if (!isDragging) {
    // Once the user is done dragging, dispatch a resize event
    raf2(() => {
      window.dispatchEvent(new Event("resize"));
    });
  }
}
