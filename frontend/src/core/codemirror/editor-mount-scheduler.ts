import {
  scheduleTask as defaultScheduleTask,
  type ScheduleTaskFn,
} from "@/utils/schedule-task";

type BuildFn = () => void;

export interface EditorMountScheduler {
  /** Queue a cell's editor build to run on a future task. */
  request(cellId: string, build: BuildFn): void;
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
  const queue = new Map<string, BuildFn>();
  const priority = new Set<string>();
  let isProcessingScheduled = false;

  function scheduleProcessing(): void {
    if (isProcessingScheduled || queue.size === 0) {
      return;
    }
    isProcessingScheduled = true;
    scheduleTask(processNext);
  }

  // Prioritized cells first, in the order they were prioritized; then FIFO.
  function nextCellId(): string | undefined {
    for (const cellId of priority) {
      if (queue.has(cellId)) {
        return cellId;
      }
      priority.delete(cellId);
    }
    return queue.keys().next().value;
  }

  function processNext(): void {
    isProcessingScheduled = false;
    const cellId = nextCellId();
    if (cellId !== undefined) {
      const build = queue.get(cellId);
      queue.delete(cellId);
      priority.delete(cellId);
      build?.();
    }
    scheduleProcessing();
  }

  return {
    request(cellId, build) {
      queue.set(cellId, build);
      scheduleProcessing();
    },
    promote(cellId) {
      const build = queue.get(cellId);
      if (build) {
        queue.delete(cellId);
        priority.delete(cellId);
        build();
      }
    },
    prioritize(cellId) {
      if (queue.has(cellId)) {
        priority.add(cellId);
      }
    },
    deprioritize(cellId) {
      priority.delete(cellId);
    },
    cancel(cellId) {
      queue.delete(cellId);
      priority.delete(cellId);
    },
  };
}

export const editorMountScheduler = createEditorMountScheduler();
