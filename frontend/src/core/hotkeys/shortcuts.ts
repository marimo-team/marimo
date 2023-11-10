/* Copyright 2023 Marimo. All rights reserved. */

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
    return satisfied;
  };
}
