/* Copyright 2026 Marimo. All rights reserved. */

import { atom, type createStore } from "jotai/vanilla";
import type { NotebookReplica } from "@/core/notebook/replica";
import { Deferred } from "@/utils/Deferred";

interface AutorunAttempt {
  phase: "preparing" | "submitted" | "settled";
}

/** Autorun an unused runtime once, using only the notebook its replica follows. */
export function createNotebookAutorun({
  store,
  replica,
  prepare,
}: {
  store: ReturnType<typeof createStore>;
  replica: NotebookReplica;
  /** Flush editor drafts; return false if a manual request has taken over. */
  prepare?: () => Promise<boolean>;
}) {
  const attemptsAtom = atom<ReadonlyMap<string, AutorunAttempt>>(new Map());
  const stateAtom = atom((get) => {
    const notebook = get(replica.notebookAtom);
    const runtime = get(replica.runtimeAtom);
    const document = get(replica.documentAtom);
    const backend = get(replica.backendAtom);
    if (
      notebook === null ||
      runtime === null ||
      document === null ||
      backend === null
    ) {
      return null;
    }
    const { runs, executions } = get(replica.executionsAtom);
    return {
      key: `${notebook.id}:${runtime.id}`,
      notebook,
      runtime,
      backend,
      runs,
      used:
        [...runs.values()].some((run) => run.runtime_id === runtime.id) ||
        [...executions.values()].some(
          ({ record }) => record.runtime_id === runtime.id,
        ),
      cells: document.revision.order,
    };
  });
  const pendingAtom = atom((get) => {
    const state = get(stateAtom);
    return state === null
      ? get(replica.notebookAtom) === null
      : get(attemptsAtom).get(state.key)?.phase !== "settled";
  });

  return {
    /** Pending until the autorun decision is made and any request reaches the stream. */
    pendingAtom,
    start({
      autoRun,
      signal,
      onError,
    }: {
      autoRun: boolean;
      signal: AbortSignal;
      onError: (error: Error) => void;
    }): void {
      async function submit(key: string) {
        const attempt: AutorunAttempt = { phase: "preparing" };
        store.set(attemptsAtom, (attempts) =>
          new Map(attempts).set(key, attempt),
        );
        const finish = () => {
          store.set(attemptsAtom, (attempts) => {
            if (attempts.get(key) !== attempt) {
              return attempts;
            }
            const next = new Map(attempts);
            if (attempt.phase === "preparing") {
              next.delete(key);
            } else {
              next.set(key, { phase: "settled" });
            }
            return next;
          });
        };
        // A remounted effect can take over a flush, but cannot undo a sent run.
        const cancel = () => {
          if (attempt.phase === "preparing") {
            finish();
          }
        };
        signal.addEventListener("abort", cancel, { once: true });
        try {
          const allowed = await prepare?.();
          if (signal.aborted) {
            return;
          }
          const state = store.get(stateAtom);
          if (
            state === null ||
            state.key !== key ||
            state.runtime.status !== "running"
          ) {
            return;
          }
          if (allowed === false || state.used || state.cells.length === 0) {
            attempt.phase = "settled";
            return;
          }
          attempt.phase = "submitted";
          const received = new Deferred<void>();
          const seen = new Set<string>();
          let runId: string | undefined;
          const observe = () => {
            const current = store.get(stateAtom);
            for (const id of current?.runs.keys() ?? []) {
              seen.add(id);
            }
            if (
              current?.key !== key ||
              (runId !== undefined && seen.has(runId))
            ) {
              received.resolve();
            }
          };
          // Observe before sending: a fast run can be pruned before its response.
          const unsubscribe = store.sub(stateAtom, observe);
          try {
            const result = await state.backend.notebook(state.notebook.id).run({
              cells: state.cells.map((id) => ({ id })),
              idempotencyKey: `startup:${key}`,
            });
            if (!result.ok) {
              // The host decides who may run. A connection it refuses,
              // such as a viewer's, has nothing to start.
              if (result.status === 403) {
                return;
              }
              throw new Error(result.problem.detail ?? result.problem.title);
            }
            // A retried request can return a run that has already ended
            // and left the stream, which will never be seen there.
            if (result.data.status === "completed") {
              return;
            }
            runId = result.data.id;
            observe();
            await received.promise;
          } finally {
            unsubscribe();
          }
        } catch (error) {
          if (!signal.aborted && store.get(stateAtom)?.key === key) {
            attempt.phase = "settled";
            onError(new Error("Failed to autorun notebook", { cause: error }));
          }
        } finally {
          signal.removeEventListener("abort", cancel);
          finish();
        }
      }

      function check() {
        if (signal.aborted) {
          return;
        }
        const state = store.get(stateAtom);
        if (state === null || store.get(attemptsAtom).has(state.key)) {
          return;
        }
        if (
          !autoRun ||
          !state.notebook.operations.includes("runtime.run") ||
          state.used ||
          (state.runtime.status !== "starting" &&
            state.runtime.status !== "running")
        ) {
          store.set(attemptsAtom, (attempts) =>
            new Map(attempts).set(state.key, { phase: "settled" }),
          );
        } else if (state.runtime.status === "running") {
          void submit(state.key);
        }
      }

      signal.throwIfAborted();
      const unsubscribeState = store.sub(stateAtom, check);
      const unsubscribeAttempts = store.sub(attemptsAtom, check);
      signal.addEventListener(
        "abort",
        () => {
          unsubscribeState();
          unsubscribeAttempts();
        },
        { once: true },
      );
      check();
    },
  };
}

export type NotebookAutorun = ReturnType<typeof createNotebookAutorun>;
