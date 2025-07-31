/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "../cells/ids";
import type { CellMessage } from "../kernel/messages";

// Virtual files are of the form /@file/<file-name>.<extension>
const VIRTUAL_FILE_REGEX = /\/@file\/([^\s/]+)\.([\dA-Za-z]+)/g;

/**
 * Tracks virtual files that are present on the page.
 */
export class VirtualFileTracker {
  /**
   * Shared instance of VirtualFileTracker since this must be a singleton.
   */
  static get INSTANCE(): VirtualFileTracker {
    const KEY = "_marimo_private_VirtualFileTracker";
    if (!window[KEY]) {
      window[KEY] = new VirtualFileTracker();
    }
    return window[KEY] as VirtualFileTracker;
  }

  virtualFiles = new Map<CellId, Set<string>>();

  private constructor() {
    // Private
  }

  track(message: Pick<CellMessage, "cell_id" | "output">): void {
    const output = message.output;
    const cellId = message.cell_id as CellId;
    if (!output) {
      return;
    }

    switch (output.mimetype) {
      case "application/json":
      case "text/html": {
        const prev = this.virtualFiles.get(cellId);
        const matches = findVirtualFiles(output.data);
        prev?.forEach((file) => matches.add(file));
        this.virtualFiles.set(cellId, matches);
        return;
      }
      default:
        return;
    }
  }

  filenames(): string[] {
    const set = new Set<string>();
    for (const files of this.virtualFiles.values()) {
      files.forEach((file) => set.add(file));
    }

    return [...set];
  }

  removeForCellId(cellId: CellId): void {
    this.virtualFiles.delete(cellId);
  }
}

// @visibleForTesting
export function findVirtualFiles(str: unknown): Set<string> {
  if (!str) {
    return new Set();
  }

  const files = new Set<string>();
  const asString = typeof str === "string" ? str : JSON.stringify(str);
  const matches = asString.match(VIRTUAL_FILE_REGEX);

  // For each match, add the file to the set of virtual files
  if (matches) {
    for (const match of matches) {
      files.add(match);
    }
  }

  return files;
}
