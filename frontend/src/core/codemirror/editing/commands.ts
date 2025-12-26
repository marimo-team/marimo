/* Copyright 2026 Marimo. All rights reserved. */
import { foldAll, unfoldAll } from "@codemirror/language";
import type { Command, EditorView } from "@codemirror/view";

type MaybeEditorView = EditorView | undefined | null;

export type BulkCommand = (targets: MaybeEditorView[]) => boolean;

/**
 * Make a bulk command from a single {@type Command} that applies
 * the given command to all targets.
 */
export function makeBulkCommand(command: Command) {
  return (targets: MaybeEditorView[]) => {
    let changed = false;
    for (const target of targets) {
      if (target) {
        changed = command(target) || changed;
      }
    }
    return changed;
  };
}

export const foldAllBulk = makeBulkCommand(foldAll);
export const unfoldAllBulk = makeBulkCommand(unfoldAll);
