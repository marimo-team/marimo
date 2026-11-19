/* Copyright 2026 Marimo. All rights reserved. */

import type { Execution } from "@marimo-team/client/protocol";
import { type CellId, SCRATCH_CELL_ID } from "../cells/ids";
import type {
  OutputMessage,
  NotificationMessageData,
} from "../kernel/messages";

// Virtual files are of the form /@file/<file-name>.<extension>
const VIRTUAL_FILE_REGEX = /\/@file\/([^\s"&'/]+)\.([\dA-Za-z]+)/g;

/**
 * Tracks virtual files that are present on the page.
 */
export class VirtualFileTracker {
  /**
   * Shared instance of VirtualFileTracker since this must be a singleton.
   */
  public static get INSTANCE(): VirtualFileTracker {
    const KEY = "_marimo_private_VirtualFileTracker";
    if (!window[KEY]) {
      window[KEY] = new VirtualFileTracker();
    }
    return window[KEY] as VirtualFileTracker;
  }

  public virtualFiles = new Map<CellId, Set<string>>();
  private callbackFiles = new Map<CellId, Set<string>>();

  private constructor() {
    // Private
  }

  public track(message: { cell_id: CellId; output: OutputMessage }): void {
    this.trackValue(message.cell_id, message.output);
  }

  public trackExecution(record: Execution): void {
    const value =
      record.outcome?.kind === "value" ? record.outcome.display : null;
    if (value) {
      this.trackValue(
        (record.cell_id as CellId | null) ?? SCRATCH_CELL_ID,
        value,
      );
    }
  }

  public trackCallbackOutput(
    message: NotificationMessageData<"callback-output">,
  ): void {
    if (message.replace || message.entries.length === 0) {
      this.callbackFiles.delete(message.cell_id);
    }
    for (const entry of message.entries) {
      this.trackValue(message.cell_id, entry, this.callbackFiles);
    }
  }

  private trackValue(
    cellId: CellId,
    output: { mimetype: string; data: unknown },
    files = this.virtualFiles,
  ): void {
    switch (output.mimetype) {
      case "application/json":
      case "text/html": {
        const prev = files.get(cellId);
        const matches = findVirtualFiles(output.data);
        prev?.forEach((file) => matches.add(file));
        files.set(cellId, matches);
        return;
      }
      default:
        return;
    }
  }

  public filenames(): string[] {
    const set = new Set<string>();
    for (const files of [
      ...this.virtualFiles.values(),
      ...this.callbackFiles.values(),
    ]) {
      files.forEach((file) => set.add(file));
    }

    return [...set];
  }

  public removeForCellId(cellId: CellId): void {
    this.virtualFiles.delete(cellId);
    this.callbackFiles.delete(cellId);
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
