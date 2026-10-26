/* Copyright 2026 Marimo. All rights reserved. */

import { idempotencyKey, type Result } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { atom, type createStore } from "jotai/vanilla";
import type { NotebookClient } from "../host/notebook-client";
import type { DocumentState, DocumentSubmission } from "./state";

/** The notebook state and operation needed by document editing. */
export type DocumentHost = Pick<NotebookClient, "documentAtom" | "edit">;

export type DocumentSyncStatus =
  | {
      readonly status:
        | "idle"
        | "pending"
        | "sending"
        | "confirming"
        | "unavailable";
    }
  | {
      readonly status: "error";
      readonly error: Error;
      readonly problem?: Protocol.Problem;
      readonly retryable: boolean;
    };

interface Submission {
  readonly submission: DocumentSubmission;
  readonly idempotencyKey: string;
  readonly startedAt: number;
  readonly controller: AbortController;
  response?: Protocol.Document;
  problem?: Protocol.Problem;
}

// The marimo host retains receipts for five minutes. Stop well before that,
// including after sleep, rather than replaying an uncertain write as a new one.
const RETRY_WINDOW_MS = 60_000;
const REQUEST_TIMEOUT_MS = 10_000;
const MAX_ATTEMPTS = 3;
const DEBOUNCE_MS = 400;

function abortable<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason);
    signal.addEventListener("abort", abort, { once: true });
    promise
      .then(resolve, reject)
      .finally(() => signal.removeEventListener("abort", abort));
    if (signal.aborted) {
      abort();
    }
  });
}

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) {
      abort();
    }
  });
}

/** Own submission scheduling; follow the existing source without opening a stream. */
export function createDocumentSync({
  store,
  notebook,
  state,
  signal,
}: {
  store: ReturnType<typeof createStore>;
  notebook: DocumentHost;
  state: DocumentState;
  signal: AbortSignal;
}) {
  signal.throwIfAborted();
  const source = notebook.documentAtom;
  const statusAtom = atom<DocumentSyncStatus>({ status: "idle" });
  const observed = atom((get) => ({
    document: get(source),
    pending: get(state.pendingAtom),
    changes: get(state.changesAtom),
  }));
  let active: Submission | null = null;
  let running: Promise<Protocol.Document> | null = null;
  let failure: Extract<DocumentSyncStatus, { status: "error" }> | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let refreshing = false;

  function clearTimer() {
    clearTimeout(timer);
    timer = undefined;
  }

  function unavailable() {
    return new Error(
      "The document or source required by an edit is unavailable",
    );
  }

  function refresh() {
    if (signal.aborted || refreshing) {
      return;
    }
    refreshing = true;
    try {
      const current = store.get(source);
      if (
        active &&
        current &&
        current.revision.notebook_id !== active.submission.notebookId
      ) {
        active.controller.abort(
          new Error("The notebook changed during synchronization"),
        );
      }
      if (running || failure) {
        return;
      }
      clearTimer();
      const changes = store.get(state.changesAtom);
      if (changes === null) {
        store.set(statusAtom, { status: "unavailable" });
      } else if (changes.length === 0) {
        // Release unsent reversals instead of keeping an invisible override.
        store.set(state.submitAtom);
        store.set(statusAtom, { status: "idle" });
      } else {
        store.set(statusAtom, { status: "pending" });
        timer = setTimeout(() => {
          void flush().catch(() => undefined);
        }, DEBOUNCE_MS);
      }
    } finally {
      refreshing = false;
    }
  }

  async function send(request: Submission) {
    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
      signal.throwIfAborted();
      request.controller.signal.throwIfAborted();
      if (Date.now() - request.startedAt >= RETRY_WINDOW_MS) {
        throw new Error(
          "The edit's retry window expired; its outcome is unknown",
        );
      }
      store.set(statusAtom, { status: "sending" });
      const controller = new AbortController();
      const abort = () => controller.abort(request.controller.signal.reason);
      request.controller.signal.addEventListener("abort", abort, {
        once: true,
      });
      const timeout = setTimeout(
        () => controller.abort(new Error("The edit request timed out")),
        REQUEST_TIMEOUT_MS,
      );
      let result: Result<Protocol.EditResponseOutput> | undefined;
      try {
        signal.throwIfAborted();
        request.controller.signal.throwIfAborted();
        result = await abortable(
          notebook.edit(
            request.submission.notebookId,
            request.submission.changes,
            {
              idempotencyKey: request.idempotencyKey,
              signal: controller.signal,
            },
          ),
          controller.signal,
        );
      } catch (error) {
        // The host may or may not have applied it. Repeat it with the same key.
        if (request.controller.signal.aborted || attempt === MAX_ATTEMPTS - 1) {
          throw error;
        }
      } finally {
        clearTimeout(timeout);
        request.controller.signal.removeEventListener("abort", abort);
      }
      signal.throwIfAborted();
      request.controller.signal.throwIfAborted();
      if (result === undefined) {
        await delay(500 * 2 ** attempt, request.controller.signal);
        continue;
      }
      // The host answered, so repeating the request returns the same answer.
      if (!result.ok) {
        request.problem = result.problem;
        throw new Error(result.problem.detail ?? result.problem.title, {
          cause: result.problem,
        });
      }
      if (result.data.document.notebook_id !== request.submission.notebookId) {
        throw new Error("Edit response belongs to another notebook");
      }
      request.response = result.data.document;
      store.set(state.settleAtom, request.submission, request.response);
      return;
    }
  }

  function confirm(request: Submission): Promise<void> {
    store.set(statusAtom, { status: "confirming" });
    return new Promise((resolve, reject) => {
      const check = () => {
        if (signal.aborted || request.controller.signal.aborted) {
          cleanup();
          reject(
            signal.aborted ? signal.reason : request.controller.signal.reason,
          );
        } else if (store.get(state.pendingAtom) !== request.submission) {
          cleanup();
          resolve();
        }
      };
      const unsubscribe = store.sub(observed, check);
      const cleanup = () => {
        unsubscribe();
        request.controller.signal.removeEventListener("abort", check);
      };
      request.controller.signal.addEventListener("abort", check, {
        once: true,
      });
      check();
    });
  }

  async function drain(
    notebookId: Protocol.NotebookId,
  ): Promise<Protocol.Document> {
    try {
      while (true) {
        signal.throwIfAborted();
        const current = store.get(source);
        if (current && current.revision.notebook_id !== notebookId) {
          throw new Error("The notebook changed during synchronization");
        }
        if (active === null) {
          if (current === null || store.get(state.changesAtom) === null) {
            throw unavailable();
          }
          const submission = store.set(state.submitAtom);
          if (submission === null) {
            return current.revision;
          }
          active = {
            submission,
            idempotencyKey: idempotencyKey(),
            startedAt: Date.now(),
            controller: new AbortController(),
          };
        }
        if (!active.response) {
          await send(active);
        }
        await confirm(active);
        active = null;
      }
    } catch (cause: unknown) {
      signal.throwIfAborted();
      const error =
        cause instanceof Error
          ? cause
          : new Error("Document synchronization failed", { cause });
      failure = {
        status: "error",
        error,
        problem: active?.problem,
        retryable:
          !signal.aborted &&
          !active?.controller.signal.aborted &&
          (active === null ||
            active.problem !== undefined ||
            Date.now() - active.startedAt < RETRY_WINDOW_MS),
      };
      if (!signal.aborted) {
        store.set(statusAtom, failure);
      }
      throw error;
    } finally {
      // Stop accepting joiners in the same turn that the drain finishes.
      running = null;
      refresh();
    }
  }

  /** Drain edits and return the revision to use as the subsequent command's precondition. */
  function flush(): Promise<Protocol.Document> {
    clearTimer();
    if (signal.aborted) {
      return Promise.reject(signal.reason);
    }
    if (failure) {
      return Promise.reject(failure.error);
    }
    if (running) {
      return running;
    }
    const notebookId =
      active?.submission.notebookId ?? store.get(source)?.revision.notebook_id;
    if (notebookId === undefined) {
      return Promise.reject(unavailable());
    }
    running = Promise.resolve().then(() => drain(notebookId));
    return running;
  }

  /** Explicitly retry a rejection against fresh state, or repeat an uncertain request exactly. */
  function retry(): Promise<Protocol.Document> {
    if (signal.aborted) {
      return Promise.reject(signal.reason);
    }
    if (!failure) {
      return flush();
    }
    if (!failure.retryable) {
      return Promise.reject(failure.error);
    }
    if (active?.problem) {
      const current = store.get(source);
      const rejectedAt = active.problem.edit?.document.version;
      if (
        !current ||
        current.revision.notebook_id !== active.submission.notebookId ||
        (rejectedAt !== undefined && current.revision.version < rejectedAt)
      ) {
        return Promise.reject(
          new Error("Wait for the host's current document before retrying"),
        );
      }
      store.set(state.settleAtom, active.submission, null);
      active = null;
    }
    failure = null;
    return flush();
  }

  const unsubscribe = store.sub(observed, refresh);
  function stop() {
    clearTimer();
    unsubscribe();
    signal.removeEventListener("abort", stop);
    active?.controller.abort(signal.reason);
  }
  signal.addEventListener("abort", stop, { once: true });
  if (signal.aborted) {
    stop();
  }
  refresh();
  return { statusAtom, flush, retry };
}
