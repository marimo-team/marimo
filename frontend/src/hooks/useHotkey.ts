/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect } from "react";

import { parseShortcut } from "../core/hotkeys/shortcuts";
import { useEventListener } from "./useEventListener";
import { useEvent } from "./useEvent";
import { useSetRegisteredAction } from "../core/hotkeys/actions";
import { HOTKEYS, HotkeyAction } from "@/core/hotkeys/hotkeys";
import { Objects } from "@/utils/objects";

type HotkeyHandler = () => boolean | void | undefined | Promise<void>;

/**
 * Registers a hotkey listener for the given shortcut.
 *
 * @param callback The callback to run when the shortcut is pressed. It does not need to be memoized as this hook will always use the latest callback.
 * If the callback returns false, preventDefault will not be called on the event.
 */
export function useHotkey(
  shortcut: HotkeyAction,
  callback: () => boolean | void | undefined
) {
  const { registerAction, unregisterAction } = useSetRegisteredAction();

  const memoizeCallback = useEvent(() => callback());

  const listener = useEvent((e: KeyboardEvent) => {
    const key = HOTKEYS.getHotkey(shortcut).key;
    if (parseShortcut(key)(e)) {
      const response = callback();
      // Prevent default if the callback does not return false
      if (response !== false) {
        e.preventDefault();
        e.stopPropagation();
      }
    }
  });

  // Register keydown listener
  useEventListener(document, "keydown", listener);

  // Register with the shortcut registry
  useEffect(() => {
    registerAction(shortcut, memoizeCallback);
    return () => unregisterAction(shortcut);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memoizeCallback, shortcut]);
}

/**
 * Registers a hotkey listener on a given element.
 */
export function useHotkeysOnElement<T extends HotkeyAction>(
  element: HTMLElement | null,
  handlers: Record<T, HotkeyHandler>
) {
  useEventListener(element, "keydown", (e) => {
    for (const [shortcut, callback] of Objects.entries(handlers)) {
      const key = HOTKEYS.getHotkey(shortcut).key;
      if (parseShortcut(key)(e)) {
        console.log("Satisfied", key, e);
        const response = callback();
        // Prevent default if the callback does not return false
        if (response !== false) {
          e.preventDefault();
          e.stopPropagation();
        }
      }
    }
  });
}
