/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect } from "react";

import { parseShortcut } from "../core/shortcuts/shortcuts";
import { useEventListener } from "./useEventListener";
import { useEvent } from "./useEvent";
import { useSetRegisteredAction } from "../core/state/actions";
import { HOTKEYS, HotkeyAction } from "@/core/hotkeys/hotkeys";

/**
 * Registers a hotkey listener for the given shortcut.
 *
 * @param callback The callback to run when the shortcut is pressed. It does not need to be memoized as this hook will always use the latest callback.
 */
export function useHotkey(shortcut: HotkeyAction, callback: () => void) {
  const { registerAction, unregisterAction } = useSetRegisteredAction();

  const memoizeCallback = useEvent(() => callback());

  const listener = useEvent((e: KeyboardEvent) => {
    const key = HOTKEYS.getHotkey(shortcut).key;
    if (parseShortcut(key)(e)) {
      e.preventDefault();
      callback();
    }
  });

  // Register keydown listener
  useEventListener("keydown", listener);

  // Register with the shortcut registry
  useEffect(() => {
    registerAction(shortcut, memoizeCallback);
    return () => unregisterAction(shortcut);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memoizeCallback, shortcut]);
}
