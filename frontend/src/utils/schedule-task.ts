/**
 * Schedules `callback` to run as a fresh task once the current task finishes,
 * letting the browser paint and handle input in between. Used to spread heavy
 * work across the event loop instead of blocking it in one long task.
 */
export type ScheduleTaskFn = (callback: () => void) => void;

/**
 * Picks the best available "yield to the event loop" primitive, preferring
 * ones that impose no artificial delay between tasks:
 *
 * 1. `scheduler.postTask` — the purpose-built Prioritized Task Scheduling API.
 *    `user-visible` runs promptly while still yielding to user-blocking input.
 * 2. `MessageChannel` — a plain macrotask with no minimum-delay clamp (nested
 *    `setTimeout` is floored at ~4ms by the spec, which would add up over many
 *    tasks).
 * 3. `setTimeout` — universal fallback; correct, just clamped when nested.
 *
 * The backend is chosen once, at module load, since it cannot change within a
 * session.
 */
// `scheduler` (the Prioritized Task Scheduling API) is not in this repo's
// lib.dom typings, so it is feature-detected behind this minimal cast.
interface PostTaskScheduler {
  postTask: (
    callback: () => void,
    options?: { priority?: "user-blocking" | "user-visible" | "background" },
  ) => Promise<unknown>;
}

function createScheduleTask(): ScheduleTaskFn {
  const scheduler = (globalThis as { scheduler?: PostTaskScheduler }).scheduler;
  if (typeof scheduler?.postTask === "function") {
    return (cb) => {
      // postTask rejects when the callback throws. Rethrow on a fresh task so a
      // thrown callback surfaces as an uncaught error, matching the
      // MessageChannel/setTimeout backends, instead of an unhandledrejection.
      void scheduler
        .postTask(cb, { priority: "user-visible" })
        .catch((error) => {
          setTimeout(() => {
            throw error;
          });
        });
    };
  }

  if (typeof MessageChannel === "function") {
    // Both ports live on this thread and no data is sent: posting a message is
    // just the cheapest way to enqueue a macrotask that yields for paint. The
    // queue lets multiple callbacks be in flight at once (one per message).
    const pending: Array<() => void> = [];
    const channel = new MessageChannel();
    channel.port1.onmessage = () => {
      pending.shift()?.();
    };

    return (cb) => {
      pending.push(cb);
      channel.port2.postMessage(null);
    };
  }

  return (cb) => {
    setTimeout(cb, 0);
  };
}

/** Shared task scheduler using the best primitive this environment offers. */
export const scheduleTask = createScheduleTask();
