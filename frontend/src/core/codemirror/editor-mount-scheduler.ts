/* Copyright 2026 Marimo. All rights reserved. */
import {
  scheduleTask as defaultScheduleTask,
  type ScheduleTaskFn,
} from "@/utils/schedule-task";

type BuildFn = () => void;

export interface EditorMountScheduler {
  /**
   * Register a cell's editor build. It stays dormant until the cell is
   * prioritized or promoted. Returns a disposer for this registration only.
   */
  register(cellId: string, build: BuildFn): () => void;
  /** Build a registered cell's editor synchronously, right now (e.g. on focus). */
  promote(cellId: string): void;
  /**
   * Queue a registered cell to build on a future task, keeping the
   * one-build-per-task pacing (e.g. when the cell scrolls into view).
   */
  prioritize(cellId: string): void;
  /** Drop a cell's queued build, leaving it registered (e.g. when it scrolls away). */
  deprioritize(cellId: string): void;
}

/**
 * Builds CodeMirror editors on demand. Registrations are dormant, so a large
 * notebook only pays for the cells that are prioritized, one build per
 * macrotask to keep the page responsive, or promoted by an explicit action.
 */
export function createEditorMountScheduler(
  scheduleTask: ScheduleTaskFn = defaultScheduleTask,
): EditorMountScheduler {
  const registrations = new Map<string, { build: BuildFn }>();
  const prioritized = new Set<string>();
  let isProcessingScheduled = false;

  function scheduleProcessing(): void {
    if (isProcessingScheduled || prioritized.size === 0) {
      return;
    }
    isProcessingScheduled = true;
    scheduleTask(processNext);
  }

  function unregister(cellId: string): void {
    registrations.delete(cellId);
    prioritized.delete(cellId);
  }

  function buildNow(cellId: string): void {
    const registration = registrations.get(cellId);
    unregister(cellId);
    registration?.build();
  }

  function processNext(): void {
    isProcessingScheduled = false;
    try {
      const next = prioritized.values().next();
      if (!next.done) {
        buildNow(next.value);
      }
    } finally {
      scheduleProcessing();
    }
  }

  return {
    register(cellId, build) {
      const registration = { build };
      unregister(cellId);
      registrations.set(cellId, registration);
      return () => {
        // An old effect's cleanup must not cancel a newer registration.
        if (registrations.get(cellId) === registration) {
          unregister(cellId);
        }
      };
    },
    promote: buildNow,
    prioritize(cellId) {
      if (registrations.has(cellId)) {
        prioritized.add(cellId);
        scheduleProcessing();
      }
    },
    deprioritize(cellId) {
      prioritized.delete(cellId);
    },
  };
}

export const editorMountScheduler = createEditorMountScheduler();
