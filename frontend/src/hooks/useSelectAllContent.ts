/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Hook that enables Ctrl/Cmd-A to select all text content within a specific element
 * @param ref - React ref to the element whose content should be selectable
 * @param enabled - Whether the hook should be active (defaults to true)
 */
export function useSelectAllContent<T extends HTMLElement>(enabled = true) {
  const handleKeyDown = (event: React.KeyboardEvent<T>) => {
    if (!enabled) {
      return;
    }

    const element = event.currentTarget;

    // Check for Ctrl-A (Windows/Linux) or Cmd-A (Mac)
    const isSelectAll =
      event.key.toLowerCase() === "a" && (event.ctrlKey || event.metaKey);

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

  return { onKeyDown: handleKeyDown };
}
