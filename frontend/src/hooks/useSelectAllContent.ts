/* Copyright 2024 Marimo. All rights reserved. */
import type { RefObject } from "react";
import { useEventListener } from "./useEventListener";

/**
 * Hook that enables Ctrl/Cmd-A to select all text content within a specific element
 * @param ref - React ref to the element whose content should be selectable
 * @param enabled - Whether the hook should be active (defaults to true)
 */
export function useSelectAllContent<T extends HTMLElement>(
  ref: RefObject<T | null>,
  enabled = true,
) {
  const handleKeyDown = (event: KeyboardEvent) => {
    if (!enabled) {
      return;
    }

    const element = ref.current;
    if (!element) {
      return;
    }

    // Check for Ctrl-A (Windows/Linux) or Cmd-A (Mac)
    const isSelectAll = event.key === "a" && (event.ctrlKey || event.metaKey);

    if (!isSelectAll) {
      return;
    }

    // Prevent default browser select-all behavior
    event.preventDefault();
    event.stopPropagation();

    // Create selection of all content within the element
    const selection = window.getSelection();
    if (!selection) {
      return;
    }

    const range = document.createRange();
    range.selectNodeContents(element);

    selection.removeAllRanges();
    selection.addRange(range);
  };

  useEventListener(ref, "keydown", handleKeyDown);
}
