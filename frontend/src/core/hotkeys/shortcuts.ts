/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";

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

export function parseShortcut(shortcut: string): (e: KeyboardEvent) => boolean {
  const keys = shortcut.split("-");
  return (e: KeyboardEvent) => {
    let satisfied = true;
    for (const character of keys) {
      switch (character) {
        case "Ctrl":
          satisfied &&= e.ctrlKey;
          break;
        case "Cmd":
          satisfied &&= e.metaKey;
          break;
        case "Shift":
          satisfied &&= e.shiftKey;
          break;
        case "Alt":
          satisfied &&= e.altKey;
          break;
        case "Space":
          satisfied &&= e.code === "Space";
          break;
        default:
          satisfied &&= e.key.toLowerCase() === character.toLowerCase();
          break;
      }

      if (!satisfied) {
        return false;
      }
    }
    if (!keys.includes("Shift")) {
      satisfied &&= !e.shiftKey;
    }
    if (!keys.includes("Ctrl")) {
      satisfied &&= !e.ctrlKey;
    }
    if (!keys.includes("Cmd")) {
      satisfied &&= !e.metaKey;
    }
    if (!keys.includes("Alt")) {
      satisfied &&= !e.altKey;
    }
    return satisfied;
  };
}

function normalizeKey(key: string): string {
  const specialKeys: { [key: string]: string } = {
    control: "ctrl",
    command: "meta",
    cmd: "meta",
    option: "alt",
    return: "enter",
    " ": "space",
  };
  return specialKeys[key.toLowerCase()] || key.toLowerCase();
}

export function isShortcutPressed(shortcut: string, e: KeyboardEvent): boolean {
  const separator = shortcut.includes("+") ? "+" : "-";
  const keys = shortcut.split(separator).map(normalizeKey);

  let satisfied = true;
  for (const key of keys) {
    switch (key) {
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
        satisfied &&= e.key.toLowerCase() === key;
        break;
    }

    if (!satisfied) {
      return false;
    }
  }

  if (!keys.includes("shift")) {
    satisfied &&= !e.shiftKey;
  }
  if (!keys.includes("ctrl")) {
    satisfied &&= !e.ctrlKey;
  }
  if (!keys.includes("meta")) {
    satisfied &&= !e.metaKey;
  }
  if (!keys.includes("alt")) {
    satisfied &&= !e.altKey;
  }

  return satisfied;
}
