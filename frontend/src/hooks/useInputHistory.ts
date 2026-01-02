/* Copyright 2026 Marimo. All rights reserved. */
import * as React from "react";

interface UseInputHistoryOptions {
  /** Current input value */
  value: string;
  /** Callback to update the input value */
  setValue: (value: string) => void;
}

interface UseInputHistoryReturn {
  /** Command history array */
  history: string[];
  /** Navigate to previous command (ArrowUp) */
  navigateUp: () => void;
  /** Navigate to next command (ArrowDown) */
  navigateDown: () => void;
  /** Add a command to history and reset navigation state */
  addToHistory: (command: string) => void;
}

/**
 * Hook for managing input command history with up/down arrow navigation.
 *
 * Features:
 * - ArrowUp navigates to previous commands
 * - ArrowDown navigates forward in history
 * - Preserves current input when starting to navigate
 * - Avoids adding duplicate consecutive commands
 */
export function useInputHistory({
  value,
  setValue,
}: UseInputHistoryOptions): UseInputHistoryReturn {
  // Command history state - using useState for reactivity
  const [history, setHistory] = React.useState<string[]>([]);
  const historyIndexRef = React.useRef<number>(-1);
  // Store the current input when navigating history
  const pendingInputRef = React.useRef<string>("");
  // Keep a ref to history for use in callbacks without causing re-renders
  const historyRef = React.useRef(history);
  historyRef.current = history;

  const navigateUp = React.useCallback(() => {
    const currentHistory = historyRef.current;
    if (currentHistory.length === 0) {
      return;
    }

    const currentIndex = historyIndexRef.current;

    // Save current input if we're starting to navigate
    if (currentIndex === -1) {
      pendingInputRef.current = value;
    }
    // Navigate to previous command
    const newIndex = Math.min(currentIndex + 1, currentHistory.length - 1);
    if (newIndex !== currentIndex) {
      historyIndexRef.current = newIndex;
      setValue(currentHistory[currentHistory.length - 1 - newIndex]);
    }
  }, [value, setValue]);

  const navigateDown = React.useCallback(() => {
    const currentHistory = historyRef.current;
    if (currentHistory.length === 0) {
      return;
    }

    const currentIndex = historyIndexRef.current;

    // Navigate to next command
    if (currentIndex > 0) {
      const newIndex = currentIndex - 1;
      historyIndexRef.current = newIndex;
      setValue(currentHistory[currentHistory.length - 1 - newIndex]);
    } else if (currentIndex === 0) {
      // Return to pending input
      historyIndexRef.current = -1;
      setValue(pendingInputRef.current);
    }
  }, [setValue]);

  const addToHistory = React.useCallback((command: string) => {
    setHistory((prev) => {
      // Add to history if it's not a duplicate of the last command
      if (prev.length === 0 || prev[prev.length - 1] !== command) {
        return [...prev, command];
      }
      return prev;
    });
    // Reset history navigation state
    historyIndexRef.current = -1;
    pendingInputRef.current = "";
  }, []);

  return {
    history,
    navigateUp,
    navigateDown,
    addToHistory,
  };
}
