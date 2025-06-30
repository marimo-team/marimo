/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import { NOT_SET } from "./hotkeys";

/**
 * Check if the current platform is Mac
 */
export function isPlatformMac() {
  if (globalThis.window === undefined) {
    Logger.warn("isPlatformMac() called without window");
    return false;
  }

  // @ts-expect-error typescript does not have types for experimental userAgentData property
  const platform = globalThis.navigator.userAgentData
    ? // @ts-expect-error typescript does not have types for experimental userAgentData property
      globalThis.navigator.userAgentData.platform
    : globalThis.navigator.platform;

  return /mac/i.test(platform);
}

function areKeysPressed(keys: string[], e: KeyboardEvent): boolean {
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

function normalizeKey(key: string): string {
  const specialKeys: { [key: string]: string } = {
    control: "ctrl",
    command: "meta",
    cmd: "meta",
    option: "alt",
    return: "enter",
  };
  return specialKeys[key.toLowerCase()] || key.toLowerCase();
}

export function parseShortcut(
  shortcut: string | typeof NOT_SET,
): (e: KeyboardEvent) => boolean {
  // Handle empty shortcut, e.g. not set
  if (shortcut === NOT_SET || shortcut === "") {
    return () => false;
  }

  const separator = shortcut.includes("+") ? "+" : "-";
  const keys = shortcut.split(separator).map(normalizeKey);
  return (e: KeyboardEvent) => areKeysPressed(keys, e);
}
