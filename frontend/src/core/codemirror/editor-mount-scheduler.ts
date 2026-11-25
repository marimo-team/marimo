/* Copyright 2026 Marimo. All rights reserved. */
import {
  scheduleTask as defaultScheduleTask,
  type ScheduleTaskFn,
} from "@/utils/schedule-task";

type BuildFn = () => void;

export interface EditorMountScheduler {
  /** Register a build. Deferred builds wait for prioritize or promote. */
  request(cellId: string, build: BuildFn, deferred?: boolean): () => void;
  /** Build a queued cell's editor synchronously, right now (e.g. on focus). */
  promote(cellId: string): void;
  /**
   * Mark a queued cell to build ahead of un-prioritized ones, keeping the
   * one-build-per-task pacing (e.g. when the cell scrolls into view).
   */
  prioritize(cellId: string): void;
  /** Drop a cell's prioritized mark, reverting it to plain FIFO order. */
  deprioritize(cellId: string): void;
  /** Remove a cell's queued build entirely. */
  cancel(cellId: string): void;
}

/**
 * Drains a FIFO queue of editor builds, one per macrotask, so constructing many
 * CodeMirror instances never blocks the main thread in a single long task. The
 * scheduler yields between every build to keep the page responsive. Cells can
 * be prioritized (e.g. when they scroll into view) to jump ahead of the queue
 * without breaking the one-build-per-macrotask pacing.
 */
export function createEditorMountScheduler(
  scheduleTask: ScheduleTaskFn = defaultScheduleTask,
): EditorMountScheduler {
  const queue = new Map<string, { build: BuildFn }>();
  const priority = new Set<string>();
  const ready = new Set<string>();
  let isProcessingScheduled = false;

  function scheduleProcessing(): void {
    if (isProcessingScheduled || nextCellId() === undefined) {
      return;
    }
    isProcessingScheduled = true;
    scheduleTask(processNext);
  }

  // Prioritized cells first, in the order they were prioritized; then FIFO.
  function nextCellId(): string | undefined {
    return priority.values().next().value ?? ready.values().next().value;
  }

  function remove(cellId: string): void {
    queue.delete(cellId);
    ready.delete(cellId);
    priority.delete(cellId);
  }

  function buildNow(cellId: string): void {
    const entry = queue.get(cellId);
    remove(cellId);
    entry?.build();
  }

  function processNext(): void {
    isProcessingScheduled = false;
    try {
      const cellId = nextCellId();
      if (cellId !== undefined) {
        buildNow(cellId);
      }
    } finally {
      scheduleProcessing();
    }
  }

  return {
    request(cellId, build, isDeferred = false) {
      const entry = { build };
      remove(cellId);
      queue.set(cellId, entry);
      if (!isDeferred) {
        ready.add(cellId);
        scheduleProcessing();
      }
      return () => {
        // An old effect's cleanup must not cancel a newer registration.
        if (queue.get(cellId) === entry) {
          remove(cellId);
        }
      };
    },
    promote: buildNow,
    prioritize(cellId) {
      if (queue.has(cellId)) {
        priority.add(cellId);
        scheduleProcessing();
      }
    },
    deprioritize(cellId) {
      priority.delete(cellId);
    },
    cancel: remove,
  };
}

export const editorMountScheduler = createEditorMountScheduler();
