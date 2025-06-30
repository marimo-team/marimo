/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "./Logger";

/**
 * Tries to copy text to the clipboard using the navigator.clipboard API.
 * If that fails, it falls back to prompting the user to copy.
 *
 * As of 2024-10-29, Safari does not support navigator.clipboard.writeText
 * when running localhost http.
 */
export async function copyToClipboard(text: string) {
  await navigator.clipboard.writeText(text).catch(async () => {
    // Fallback to prompt
    Logger.warn("Failed to copy to clipboard using navigator.clipboard");
    globalThis.prompt("Copy to clipboard: Ctrl+C, Enter", text);
  });
}
