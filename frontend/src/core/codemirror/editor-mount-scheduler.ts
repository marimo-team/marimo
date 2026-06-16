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
  cancel(cellId: string): void;
}

/**
 * Drains a FIFO queue of editor builds, one per macrotask, so constructing many
 * CodeMirror instances never blocks the main thread in a single long task. The
 * scheduler yields between every build to keep the page responsive.
 */
export function createEditorMountScheduler(
  scheduleTask: ScheduleTaskFn = defaultScheduleTask,
): EditorMountScheduler {
  const queue = new Map<string, BuildFn>();
  let isProcessingScheduled = false;

  function scheduleProcessing(): void {
    if (isProcessingScheduled || queue.size === 0) {
      return;
    }
    isProcessingScheduled = true;
    scheduleTask(processNext);
  }

  function processNext(): void {
    isProcessingScheduled = false;
    const cellId = queue.keys().next().value;
    if (cellId !== undefined) {
      const build = queue.get(cellId);
      queue.delete(cellId);
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
        build();
      }
    },
    cancel(cellId) {
      queue.delete(cellId);
    },
  };
}

export const editorMountScheduler = createEditorMountScheduler();
