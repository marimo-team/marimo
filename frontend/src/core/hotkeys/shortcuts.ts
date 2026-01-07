/* Copyright 2026 Marimo. All rights reserved. */

import type { KeyBinding } from "@codemirror/view";
import { Logger } from "@/utils/Logger";
import { NOT_SET } from "./hotkeys";

/**
 * Check if the current platform is Mac
 */
export function isPlatformMac() {
  if (typeof window === "undefined") {
    Logger.warn("isPlatformMac() called without window");
    return false;
  }

  // @ts-expect-error typescript does not have types for experimental userAgentData property
  const platform = window.navigator.userAgentData
    ? // @ts-expect-error typescript does not have types for experimental userAgentData property
      window.navigator.userAgentData.platform
    : window.navigator.platform;

  return /mac/i.test(platform);
}

/**
 * Check if the current platform is Windows
 */
export function isPlatformWindows() {
  if (typeof window === "undefined") {
    Logger.warn("isPlatformWindows() called without window");
    return false;
  }
  // @ts-expect-error typescript does not have types for experimental userAgentData property
  const platform = window.navigator.userAgentData
    ? // @ts-expect-error typescript does not have types for experimental userAgentData property
      window.navigator.userAgentData.platform
    : window.navigator.platform;

  return /win/i.test(platform);
}

type IKeyboardEvent = Pick<
  KeyboardEvent,
  "key" | "shiftKey" | "ctrlKey" | "metaKey" | "altKey" | "code"
>;

function areKeysPressed(keys: string[], e: IKeyboardEvent): boolean {
  let satisfied = true;
  for (const key of keys) {
    switch (key) {
      case "mod":
        // Accept both meta and ctrl
        satisfied &&= e.metaKey || e.ctrlKey;
        break;
      case "ctrl":
        satisfied &&= e.ctrlKey;
        break;
      case "meta":
        satisfied &&= e.metaKey;
        break;
      case "shift":
        satisfied &&= e.shiftKey;
        break;
      case "alt":
        satisfied &&= e.altKey;
        break;
      case "space":
        satisfied &&= e.code === "Space";
        break;
      default:
        // Handle digit keys specially when shift is pressed
        // Shift+7 produces different characters across keyboards/platforms:
        // - US keyboards: "&"
        // - Some layouts: "7"
        // Using e.code (physical key) instead of e.key (produced character)
        // eslint-disable-next-line unicorn/prefer-ternary
        if (/^\d$/.test(key) && e.shiftKey) {
          satisfied &&= e.code === `Digit${key}`;
        } else {
          satisfied &&= e.key.toLowerCase() === key;
        }
        break;
    }

    if (!satisfied) {
      return false;
    }
  }

  // If the shortcut does not include a modifier, ensure the modifier is not pressed
  if (!keys.includes("shift")) {
    satisfied &&= !e.shiftKey;
  }
  if (!keys.includes("ctrl") && !keys.includes("mod")) {
    satisfied &&= !e.ctrlKey;
  }
  if (!keys.includes("meta") && !keys.includes("mod")) {
    satisfied &&= !e.metaKey;
  }
  if (!keys.includes("alt")) {
    satisfied &&= !e.altKey;
  }

  return satisfied;
}

function normalizeKey(key: string): string {
  const specialKeys: { [key: string]: string } = {
    control: "ctrl",
    command: "mod",
    cmd: "mod",
    option: "alt",
    return: "enter",
  };
  return specialKeys[key.toLowerCase()] || key.toLowerCase();
}

/**
 * Returns a function that checks if a shortcut is pressed.
 *
 * @param shortcut - The shortcut to check.
 * @returns A function that checks if the shortcut is pressed.
 */
export function parseShortcut(
  shortcut: string | typeof NOT_SET,
): (e: IKeyboardEvent) => boolean {
  // Handle empty shortcut, e.g. not set
  if (shortcut === NOT_SET || shortcut === "") {
    return () => false;
  }

  const separator = shortcut.includes("+") ? "+" : "-";
  const keys = shortcut.split(separator).map(normalizeKey);
  return (e: IKeyboardEvent) => areKeysPressed(keys, e);
}

export type Platform = "mac" | "windows" | "linux";

export function resolvePlatform(): Platform {
  if (isPlatformMac()) {
    return "mac";
  }
  if (isPlatformWindows()) {
    return "windows";
  }
  return "linux";
}

/**
 * On macOS, duplicate a Cmd-based keybinding to also work with Ctrl.
 * This allows users coming from Jupyter/Colab to use Ctrl-Enter to run cells.
 *
 * Returns an array with the original binding, plus a Ctrl variant on macOS.
 * For use with CodeMirror keymap bindings.
 *
 * Design decision: User-defined Cmd shortcuts also get Ctrl equivalents.
 * The edge case is if a user wants `Cmd+<x>` and `Ctrl+<x>` to trigger
 * different actions, this isn't currently supported. Given the relatively
 * small number of keymaps, we're keeping this simple. If it becomes an issue,
 * we can refactor to resolve a special "Mod" key internally and require users
 * to specify explicit single-key mappings.
 *
 * Note: If the binding already contains Ctrl (e.g., Cmd-Ctrl-Enter),
 * no duplication is done to avoid producing invalid Ctrl-Ctrl-key combos.
 */
export function duplicateWithCtrlModifier<T extends KeyBinding>(
  binding: T,
): T[] {
  // Skip if not macOS, not a Cmd binding, or already has Ctrl
  if (
    !isPlatformMac() ||
    !binding.key?.includes("Cmd") ||
    binding.key.includes("Ctrl")
  ) {
    return [binding];
  }
  return [binding, { ...binding, key: binding.key.replaceAll("Cmd", "Ctrl") }];
}
