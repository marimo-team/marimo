/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtomValue, useSetAtom } from "jotai";
import useEvent from "react-use-event-hook";
import type { HotkeyAction } from "@/core/hotkeys/hotkeys";

/**
 * Map of registered keyboard shortcuts and their callbacks.
 */
const registeredActionsAtom = atom<
  Partial<Record<HotkeyAction, (() => void) | undefined>>
>({});

/**
 * Returns the map of registered keyboard shortcuts and their callbacks.
 */
export function useRegisteredActions() {
  return useAtomValue(registeredActionsAtom);
}

/**
 * Returns a hook for registering keyboard shortcuts.
 */
export function useSetRegisteredAction() {
  const set = useSetAtom(registeredActionsAtom);
  return {
    registerAction: useEvent(
      (shortcut: HotkeyAction, callback: (evt?: KeyboardEvent) => void) => {
        set((actions) => ({ ...actions, [shortcut]: callback }));
      },
    ),
    unregisterAction: useEvent((shortcut: HotkeyAction) => {
      set((actions) => {
        const { [shortcut]: unused, ...rest } = actions;
        return rest;
      });
    }),
  };
}
