/* Copyright 2026 Marimo. All rights reserved. */

import { idempotencyKey } from "@marimo-team/client";
import { atom, type Atom, type createStore } from "jotai/vanilla";
import type { NotebookBackend, NotebookReplica } from "../replica";

interface Draft {
  readonly value: unknown;
  readonly requestId: string;
  readonly backend: NotebookBackend;
}

export interface UIElementModel {
  readonly valuesAtom: Atom<ReadonlyMap<string, unknown>>;
  update(id: string, value: unknown): Promise<void>;
  start(options: { signal: AbortSignal }): void;
}

/** Local input survives older echoes; only its own kernel echo settles it. */
export function createUIElementModel({
  store,
  replica,
}: {
  store: ReturnType<typeof createStore>;
  replica: Pick<
    NotebookReplica,
    "uiElementsAtom" | "backendAtom" | "notebookAtom"
  >;
}): UIElementModel {
  const draftsAtom = atom<ReadonlyMap<string, Draft>>(new Map());
  let lifetime: AbortSignal | undefined;
  const valuesAtom = atom((get) => {
    const drafts = get(draftsAtom);
    return new Map(
      [...get(replica.uiElementsAtom)].map(([id, confirmed]) => {
        const draft = drafts.get(id);
        return [id, draft ? draft.value : confirmed.element.state.value];
      }),
    );
  });

  function clear(id: string, draft: Draft) {
    const current = store.get(draftsAtom);
    if (current.get(id) === draft) {
      const next = new Map(current);
      next.delete(id);
      store.set(draftsAtom, next);
    }
  }

  return {
    valuesAtom,
    start({ signal }) {
      signal.throwIfAborted();
      if (lifetime && !lifetime.aborted) {
        throw new Error("UI element model is already started");
      }
      lifetime = signal;
      const reconcile = () => {
        const confirmed = store.get(replica.uiElementsAtom);
        const backend = store.get(replica.backendAtom);
        for (const [id, draft] of store.get(draftsAtom)) {
          const record = confirmed.get(id);
          if (
            !record ||
            backend !== draft.backend ||
            record.requestId === draft.requestId
          ) {
            clear(id, draft);
          }
        }
      };
      const unsubscribeRecords = store.sub(replica.uiElementsAtom, reconcile);
      const unsubscribeBackend = store.sub(replica.backendAtom, reconcile);
      signal.addEventListener(
        "abort",
        () => {
          unsubscribeRecords();
          unsubscribeBackend();
          store.set(draftsAtom, new Map());
        },
        { once: true },
      );
    },
    async update(id, value) {
      const signal = lifetime;
      const backend = store.get(replica.backendAtom);
      const notebook = store.get(replica.notebookAtom);
      if (
        !signal ||
        signal.aborted ||
        !backend ||
        !notebook?.operations.includes("ui_element.update") ||
        !store.get(replica.uiElementsAtom).has(id)
      ) {
        throw new Error("UI element updates are unavailable");
      }
      // Capture the destination before publishing the draft to subscribers.
      const commands = backend.notebook(notebook.id);
      const draft = { value, requestId: idempotencyKey(), backend };
      store.set(draftsAtom, new Map(store.get(draftsAtom)).set(id, draft));
      try {
        const response = await commands.updateUIElement(
          id,
          { value },
          {
            idempotencyKey: draft.requestId,
            signal,
          },
        );
        if (!response.ok) {
          throw new Error(response.problem.detail ?? response.problem.title);
        }
        // HTTP acceptance may arrive before or after the matching stream event.
      } catch (error) {
        clear(id, draft);
        throw error;
      }
    },
  };
}
