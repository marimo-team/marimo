/* Copyright 2024 Marimo. All rights reserved. */
import { DEFAULT_CELL_NAME } from "@/core/cells/names";

export function createCellLink(cellName: string): string {
  const url = new URL(window.location.href);
  // Add the cell name to the hash parameter
  url.hash = `scrollTo=${encodeURIComponent(cellName)}`;
  return url.toString();
}

/**
 * Extract cell name from URL hash
 */
export function extractCellNameFromHash(hash: string): string | null {
  const scrollToMatch = hash.match(/scrollTo=([^&]+)/);
  const cellName = scrollToMatch?.[1];
  if (cellName) {
    return decodeURIComponent(cellName.split("&")[0]);
  }
  return null;
}

/**
 * Check if a cell can be linked to (requires a name)
 */
export function canLinkToCell(cellName: string | undefined): boolean {
  if (cellName === DEFAULT_CELL_NAME) {
    return false;
  }
  return Boolean(cellName && cellName.trim().length > 0);
}
