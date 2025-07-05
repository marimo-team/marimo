/* Copyright 2024 Marimo. All rights reserved. */

export function copyShortcutPressed(e: React.KeyboardEvent<HTMLElement>) {
  return isModifierKey(e) && e.key === "c";
}

export function pasteShortcutPressed(e: React.KeyboardEvent<HTMLElement>) {
  return isModifierKey(e) && e.key === "v";
}

export function isModifierKey(e: React.KeyboardEvent<HTMLElement>) {
  return e.metaKey || e.ctrlKey;
}
