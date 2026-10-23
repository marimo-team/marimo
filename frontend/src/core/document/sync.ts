/* Copyright 2026 Marimo. All rights reserved. */

import { idempotencyKey, type Result } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { atom, type Atom, type createStore } from "jotai/vanilla";
import type { Document } from "../host/resources/document";
import type { DocumentModel, DocumentSubmission } from "./model";

/**
 * The part of a host client that synchronization uses.
 *
 * A `Client` from `@marimo-team/client` satisfies it. The session supplies
 * authenticated access to one host for the model's lifetime.
 */
export interface DocumentHost {
  notebook(id: Protocol.NotebookId): {
    edit(
      changes: readonly Protocol.Change[],
      options: {
        readonly idempotencyKey: string;
        readonly signal: AbortSignal;
      },
    ): Promise<Result<Protocol.EditResponseOutput>>;
  };
}

export type DocumentSyncState =
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
  readonly edit: DocumentSubmission;
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
  source,
  model,
  host,
  signal,
}: {
  store: ReturnType<typeof createStore>;
  source: Atom<Document | null>;
  model: DocumentModel;
  host: DocumentHost;
  signal?: AbortSignal;
}) {
  const stateAtom = atom<DocumentSyncState>({ status: "idle" });
  const observed = atom((get) => ({
    document: get(source),
    pending: get(model.pendingAtom),
    changes: get(model.changesAtom),
  }));
  let active: Submission | null = null;
  let running: Promise<Protocol.Document> | null = null;
  let failure: Extract<DocumentSyncState, { status: "error" }> | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;
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
    if (disposed || refreshing) {
      return;
    }
    refreshing = true;
    try {
      const current = store.get(source);
      if (
        active &&
        current &&
        current.revision.notebook_id !== active.edit.notebookId
      ) {
        active.controller.abort(
          new Error("The notebook changed during synchronization"),
        );
      }
      if (running || failure) {
        return;
      }
      clearTimer();
      const changes = store.get(model.changesAtom);
      if (changes === null) {
        store.set(stateAtom, { status: "unavailable" });
      } else if (changes.length === 0) {
        // Release unsent reversals instead of keeping an invisible override.
        store.set(model.submitAtom);
        store.set(stateAtom, { status: "idle" });
      } else {
        store.set(stateAtom, { status: "pending" });
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
      request.controller.signal.throwIfAborted();
      if (Date.now() - request.startedAt >= RETRY_WINDOW_MS) {
        throw new Error(
          "The edit's retry window expired; its outcome is unknown",
        );
      }
      store.set(stateAtom, { status: "sending" });
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
        result = await abortable(
          host.notebook(request.edit.notebookId).edit(request.edit.changes, {
            idempotencyKey: request.idempotencyKey,
            signal: controller.signal,
          }),
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
      if (result.data.document.notebook_id !== request.edit.notebookId) {
        throw new Error("Edit response belongs to another notebook");
      }
      request.response = result.data.document;
      store.set(model.settleAtom, request.edit, request.response);
      return;
    }
  }

  function confirm(request: Submission): Promise<void> {
    store.set(stateAtom, { status: "confirming" });
    return new Promise((resolve, reject) => {
      const check = () => {
        if (request.controller.signal.aborted) {
          cleanup();
          reject(request.controller.signal.reason);
        } else if (store.get(model.pendingAtom) !== request.edit) {
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
    while (true) {
      if (disposed) {
        throw new Error("Document synchronization was disposed");
      }
      const current = store.get(source);
      if (current && current.revision.notebook_id !== notebookId) {
        throw new Error("The notebook changed during synchronization");
      }
      if (active === null) {
        if (current === null || store.get(model.changesAtom) === null) {
          throw unavailable();
        }
        const edit = store.set(model.submitAtom);
        if (edit === null) {
          return current.revision;
        }
        active = {
          edit,
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
  }

  /** Drain edits and return the revision to use as the subsequent command's precondition. */
  function flush(): Promise<Protocol.Document> {
    clearTimer();
    if (disposed) {
      return Promise.reject(new Error("Document synchronization was disposed"));
    }
    if (failure) {
      return Promise.reject(failure.error);
    }
    if (running) {
      return running;
    }
    const notebookId =
      active?.edit.notebookId ?? store.get(source)?.revision.notebook_id;
    if (notebookId === undefined) {
      return Promise.reject(unavailable());
    }
    running = Promise.resolve()
      .then(() => drain(notebookId))
      .catch((cause: unknown) => {
        const error =
          cause instanceof Error
            ? cause
            : new Error("Document synchronization failed", { cause });
        failure = {
          status: "error",
          error,
          problem: active?.problem,
          retryable:
            !disposed &&
            !active?.controller.signal.aborted &&
            (active === null ||
              active.problem !== undefined ||
              Date.now() - active.startedAt < RETRY_WINDOW_MS),
        };
        if (!disposed) {
          store.set(stateAtom, failure);
        }
        throw error;
      })
      .finally(() => {
        running = null;
        refresh();
      });
    return running;
  }

  /** Explicitly retry a rejection against fresh state, or repeat an uncertain request exactly. */
  function retry(): Promise<Protocol.Document> {
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
        current.revision.notebook_id !== active.edit.notebookId ||
        (rejectedAt !== undefined && current.revision.version < rejectedAt)
      ) {
        return Promise.reject(
          new Error("Wait for the host's current document before retrying"),
        );
      }
      store.set(model.settleAtom, active.edit, null);
      active = null;
    }
    failure = null;
    return flush();
  }

  const unsubscribe = store.sub(observed, refresh);
  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    clearTimer();
    unsubscribe();
    signal?.removeEventListener("abort", dispose);
    active?.controller.abort(
      new Error("Document synchronization was disposed"),
    );
  }
  signal?.addEventListener("abort", dispose, { once: true });
  if (signal?.aborted) {
    dispose();
  }
  refresh();
  return { stateAtom, flush, retry, dispose };
}
