/* Copyright 2026 Marimo. All rights reserved. */

import { mapWithConcurrency } from "./semaphore";

const FILE_READ_CONCURRENCY = 5;

/**
 * Converts a Blob or File to either a base64-encoded string or a data URL.
 *
 * @param input - The Blob or File to convert.
 * @param format - The output format: "base64" for the base64-encoded string, "dataUrl" for the full data URL.
 * @returns A promise that resolves to the requested string representation.
 */
export function blobToString(
  input: Blob | File,
  format: "base64" | "dataUrl",
): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.readAsDataURL(input);
    reader.onload = (e) => {
      if (e.target?.result) {
        const dataURL = e.target.result as string;
        if (format === "base64") {
          // Extract base64 content from data URL. data:*/*;base64,contents
          const base64Content = dataURL.slice(dataURL.indexOf(",") + 1);
          resolve(base64Content);
        } else {
          resolve(dataURL);
        }
      }
    };
  });
}

/**
 * Read contents of files as base64-encoded strings
 *
 * Returns a promised array of tuples [file name, file contents].
 */
export function filesToBase64(files: File[]): Promise<[string, string][]> {
  return mapWithConcurrency(files, FILE_READ_CONCURRENCY, async (file) => {
    const contents = await blobToString(file, "base64");
    return [file.name, contents] as [string, string];
  });
}
