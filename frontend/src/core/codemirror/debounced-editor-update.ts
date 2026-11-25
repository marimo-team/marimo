/* Copyright 2026 Marimo. All rights reserved. */
import type { TransactionSpec } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { debounce } from "lodash-es";

/**
 * Coalesce invalidations and compute against the latest state outside CM's
 * update cycle. Return undefined from compute when nothing needs dispatching.
 * destroy cancels both the timer and any already queued microtask.
 */
export function createDebouncedEditorUpdate(
  view: EditorView,
  compute: () => TransactionSpec | undefined,
  delay = 300,
) {
  let destroyed = false;
  let generation = 0;
  const run = debounce((scheduledGeneration: number) => {
    queueMicrotask(() => {
      if (destroyed || scheduledGeneration !== generation) {
        return;
      }
      const transaction = compute();
      if (transaction) {
        view.dispatch(transaction);
      }
    });
  }, delay);
  return {
    schedule() {
      if (!destroyed) {
        run(++generation);
      }
    },
    destroy() {
      destroyed = true;
      generation++;
      run.cancel();
    },
  };
}
