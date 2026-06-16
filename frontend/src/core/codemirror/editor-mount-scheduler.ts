type BuildFn = () => void;

// Runs a callback as its own macrotask, letting the browser paint in between.
type ScheduleTaskFn = (callback: () => void) => void;

// A prompt macrotask scheduler: the callback runs as soon as the current task
// finishes, without waiting for the main thread to go idle (which starves
// under sustained load) and while still letting the browser paint in between.
const defaultScheduleTask: ScheduleTaskFn = (() => {
  if (typeof MessageChannel !== "function") {
    return (callback) => {
      setTimeout(callback, 0);
    };
  }
  let scheduled: (() => void) | null = null;
  const channel = new MessageChannel();
  channel.port1.onmessage = () => {
    const callback = scheduled;
    scheduled = null;
    callback?.();
  };
  return (callback) => {
    scheduled = callback;
    channel.port2.postMessage(null);
  };
})();

export interface EditorMountScheduler {
  request(cellId: string, build: BuildFn): void;
  promote(cellId: string): void;
  prioritize(cellId: string): void;
  deprioritize(cellId: string): void;
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
