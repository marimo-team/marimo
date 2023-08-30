/* Copyright 2023 Marimo. All rights reserved. */
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
    if (lastFocused instanceof HTMLElement) {
      lastFocused.focus();
    }
    evt.preventDefault();
  };

  return { onOpenAutoFocus, onCloseAutoFocus };
}
