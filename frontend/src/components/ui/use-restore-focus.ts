/* Copyright 2024 Marimo. All rights reserved. */
import { useState } from "react";

/**
 * Hook to restore focus to the element that was focused before the current,
 * specifically for Radix Dialogs.
 */
export function useRestoreFocus() {
  // store the last focused element so we can restore it when the dialog closes
  const [lastFocused, setLastFocused] = useState<Element | null>(null);

  const onOpenAutoFocus = () => {
    setLastFocused(document.activeElement);
  };

  const onCloseAutoFocus = (evt: Event) => {
    // If the current focus is the body, restore focus to the last focused element
    if (document.activeElement !== document.body) {
      return;
    }
    if (lastFocused instanceof HTMLElement) {
      lastFocused.focus();
    }
    evt.preventDefault();
  };

  return { onOpenAutoFocus, onCloseAutoFocus };
}
