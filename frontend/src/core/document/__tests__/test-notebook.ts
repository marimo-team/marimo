/* Copyright 2026 Marimo. All rights reserved. */

import type { Result } from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { atom, type createStore } from "jotai/vanilla";
import { vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { invariant } from "@/utils/invariant";
import { type FakeEdit, fakeBackend } from "../../host/__tests__/fixtures";
import type { Document } from "../../host/resources/document";
import { createTestHost, type EditRequest } from "./test-host";

export interface PendingRequest extends EditRequest {
  readonly signal: AbortSignal;
  process(): void;
  deliverResponse(): void;
  loseResponse(): void;
}

export function createTestNotebook(
  store: ReturnType<typeof createStore>,
  initial: Document,
) {
  const host = createTestHost(initial);
  const source = atom<Document | null>(initial);
  const requests: PendingRequest[] = [];
  const waiting: Deferred<PendingRequest>[] = [];
  const documents: Document[] = [];
  function apply(changes: readonly Protocol.Change[]) {
    const { result, update } = host.apply(changes);
    invariant(result.ok, "Another writer's edit was rejected");
    if (update !== undefined) {
      documents.push(update);
    }
  }
  const edit = vi.fn<FakeEdit>((notebookId, changes, options) => {
    const signal = options?.signal;
    const idempotencyKey = options?.idempotencyKey;
    invariant(
      signal !== undefined && idempotencyKey !== undefined,
      "The test host answers edits that carry a key and a signal",
    );
    signal.throwIfAborted();
    const reply = new Deferred<Result<Protocol.EditResponseOutput>>();
    let outcome: Result<Protocol.EditResponseOutput> | undefined;
    const abort = () => reply.reject(signal.reason);
    const finish = () => signal.removeEventListener("abort", abort);
    signal.addEventListener("abort", abort, { once: true });
    void reply.promise.then(finish, finish);
    const request: PendingRequest = {
      notebookId,
      changes: structuredClone(changes),
      idempotencyKey,
      signal,
      process() {
        invariant(outcome === undefined, "Request was already processed");
        // Cancellation of the client's wait does not roll back a server commit.
        const processed = host.process(request);
        outcome = processed.result;
        if (processed.update !== undefined) {
          documents.push(processed.update);
        }
      },
      deliverResponse() {
        invariant(
          outcome !== undefined,
          "Process the request before delivering its response",
        );
        reply.resolve(outcome);
      },
      loseResponse() {
        reply.reject(new Error("Connection lost"));
      },
    };
    const next = waiting.shift();
    if (next === undefined) {
      requests.push(request);
    } else {
      next.resolve(request);
    }
    return reply.promise;
  });
  const notebook = {
    documentAtom: source,
    backendAtom: atom(fakeBackend({ edit })),
    edit,
  };
  return {
    notebook,
    control: {
      document: host.document,
      nextRequest(): Promise<PendingRequest> {
        const next = requests.shift();
        if (next !== undefined) {
          return Promise.resolve(next);
        }
        const deferred = new Deferred<PendingRequest>();
        waiting.push(deferred);
        return deferred.promise;
      },
      changeCell(
        id: Protocol.CellId,
        patch: Partial<Omit<Protocol.CellInput, "id">>,
      ) {
        const cell = host.document().cells.get(id);
        invariant(
          cell !== undefined && cell.code !== null,
          `No host source for cell ${id}`,
        );
        apply([
          {
            kind: "put_cell",
            base_etag: cell.etag,
            cell: {
              ...cell,
              code: cell.code,
              ...patch,
              config: { ...cell.config, ...patch.config },
            },
          },
        ]);
      },
      createCell(cell: Protocol.CellInput) {
        apply([{ kind: "put_cell", base_etag: null, cell }]);
      },
      deleteCell(id: Protocol.CellId) {
        const cell = host.document().cells.get(id);
        invariant(cell !== undefined, `No host cell ${id}`);
        apply([{ kind: "delete_cell", id, base_etag: cell.etag }]);
      },
      deliverDocument() {
        const next = documents.shift();
        invariant(
          next !== undefined,
          "No document update is waiting for delivery",
        );
        store.set(source, next);
      },
      reset() {
        documents.length = 0;
        store.set(source, null);
      },
      deliverSnapshot() {
        documents.length = 0;
        store.set(source, host.document());
      },
    },
  };
}
