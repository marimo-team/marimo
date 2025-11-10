/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import { useEventListener } from "@/hooks/useEventListener";

/**
 * Hook to manage the visibility of island controls based on keyboard state.
 *
 * Controls are shown when:
 * - alwaysShowRun is true, OR
 * - User holds Cmd/Ctrl key
 *
 * @param alwaysShowRun - If true, controls are always visible
 * @returns Whether controls should be shown
 */
export function useIslandControls(alwaysShowRun: boolean): boolean {
  const [pressed, setPressed] = useState<boolean>(alwaysShowRun);

  // No need to register if display is always on
  const maybeNoop = <T>(fn: (e: T) => void) =>
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    alwaysShowRun ? () => {} : fn;

  useEventListener(
    document,
    "keydown",
    maybeNoop((e: KeyboardEvent) => {
      if (!alwaysShowRun && (e.metaKey || e.ctrlKey)) {
        setPressed(true);
      }
    }),
  );

  useEventListener(
    document,
    "keyup",
    maybeNoop((e: KeyboardEvent) => {
      if (
        !alwaysShowRun &&
        (e.metaKey || e.ctrlKey || e.key === "Meta" || e.key === "Control")
      ) {
        setPressed(false);
      }
    }),
  );

  // Set pressed to false if the window loses focus
  useEventListener(window, "blur", () => setPressed(false));
  useEventListener(window, "mouseleave", () => setPressed(false));

  return pressed;
}
