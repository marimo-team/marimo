/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "./Logger";

declare global {
  interface Window {
    [key: string]: unknown;
  }
}

/**
 * Safely adds objects to the global scope for debugging.
 */
export function repl(item: unknown, name: string) {
  if (globalThis.window === undefined) {
    return;
  }

  const fullName = `__marimo__${name}`;
  if (window[fullName] && process.env.NODE_ENV !== "test") {
    Logger.warn(`Overwriting existing debug object ${fullName}`);
  }
  window[fullName] = item;
}
