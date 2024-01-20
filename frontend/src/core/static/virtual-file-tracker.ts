/* Copyright 2024 Marimo. All rights reserved. */
import { CellMessage } from "../kernel/messages";
import { CellId } from "../cells/ids";
import { repl } from "@/utils/repl";

// Virtual files are of the form /@file/<file-name>.<extension>
const VIRTUAL_FILE_REGEX = /\/@file\/([^\s/]+)\.([\dA-Za-z]+)/g;

/**
 * Tracks virtual files that are present on the page.
 */
export class VirtualFileTracker {
  /**
   * Shared instance of VirtualFileTracker since this must be a singleton.
   */
  static readonly INSTANCE = new VirtualFileTracker();

  virtualFiles = new Map<CellId, Set<string>>();

  private constructor() {
    repl(VirtualFileTracker.INSTANCE, "VirtualFileTracker");
  }

  track(message: Pick<CellMessage, "cell_id" | "output">): void {
    const { cell_id, output } = message;
    if (!output) {
      return;
    }

    switch (output.mimetype) {
      case "application/json":
      case "text/html": {
        const prev = this.virtualFiles.get(cell_id);
        const matches = findVirtualFiles(output.data);
        prev?.forEach((file) => matches.add(file));
        this.virtualFiles.set(cell_id, matches);
        return;
      }
      default:
        return;
    }
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
