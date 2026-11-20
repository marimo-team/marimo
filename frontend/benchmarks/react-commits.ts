/* Copyright 2026 Marimo. All rights reserved. */

import type { Page } from "@playwright/test";

interface RenderedComponent {
  name: string;
  cellId: string | null;
  changedProps: string[];
}

interface Commit {
  phase: string;
  renderDuration: number;
  components: RenderedComponent[];
}

interface CommitRecorder {
  version: string;
  commits: Commit[];
  reset: () => void;
}

declare global {
  interface Window {
    editingCommits?: CommitRecorder;
  }
}

// This diagnostic uses React's private DevTools hook and Fiber fields.
// Revalidate it after React upgrades; it is not an application dependency.
export async function installReactCommitRecorder(page: Page) {
  await page.addInitScript(() => {
    interface ComponentType {
      name?: string;
      displayName?: string;
      render?: ComponentType;
      type?: ComponentType;
    }
    interface Fiber {
      tag: number;
      flags: number;
      type: ComponentType | null;
      memoizedProps: Record<string, unknown> | null;
      alternate: Fiber | null;
      child: Fiber | null;
      sibling: Fiber | null;
      actualDuration: number;
    }

    const recorder: CommitRecorder = {
      version: "",
      commits: [],
      reset() {
        recorder.commits.length = 0;
      },
    };
    window.editingCommits = recorder;
    Object.assign(window, {
      __REACT_DEVTOOLS_GLOBAL_HOOK__: {
        supportsFiber: true,
        inject(renderer: { version: string }) {
          recorder.version = renderer.version;
          return 1;
        },
        onCommitFiberRoot(_renderer: number, root: { current: Fiber }) {
          // Only record the measured window, after mounting and warmup.
          if (!window.editingMetrics || recorder.commits.length >= 1000) {
            return;
          }
          const components: RenderedComponent[] = [];
          function visit(fiber: Fiber, inheritedCellId: string | null) {
            const previous = fiber.alternate;
            const cellId =
              typeof fiber.memoizedProps?.cellId === "string"
                ? fiber.memoizedProps.cellId
                : inheritedCellId;
            // PerformedWork identifies rendered function/class/memo components.
            if (
              [0, 1, 11, 14, 15].includes(fiber.tag) &&
              (fiber.flags & 1) !== 0
            ) {
              const type = fiber.type;
              const name =
                type?.displayName ??
                type?.name ??
                type?.render?.displayName ??
                type?.render?.name ??
                type?.type?.name ??
                "Anonymous";
              const props = fiber.memoizedProps ?? {};
              const previousProps = previous?.memoizedProps ?? {};
              components.push({
                name,
                cellId,
                changedProps: Object.keys({
                  ...previousProps,
                  ...props,
                }).filter((key) => !Object.is(props[key], previousProps[key])),
              });
            }
            // A bailed-out parent can reuse its entire previous child list.
            // Do not count stale flags in that reused subtree as new renders.
            if (fiber.child !== previous?.child) {
              for (let child = fiber.child; child; child = child.sibling) {
                visit(child, cellId);
              }
            }
          }
          visit(root.current, null);
          recorder.commits.push({
            phase: window.editingMetrics.phase,
            renderDuration: root.current.actualDuration,
            components,
          });
        },
      },
    });
  });
}
