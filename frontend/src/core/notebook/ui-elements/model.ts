/* Copyright 2026 Marimo. All rights reserved. */

import { idempotencyKey } from "@marimo-team/client";
import type { UIElementOutput } from "@marimo-team/client/protocol";
import { atom, type Atom, type createStore } from "jotai/vanilla";
import {
  createHostFunctionRequest,
  type FunctionRequest,
} from "@/core/functions/host-function";
import type { NotebookBackend, NotebookReplica } from "../replica";

interface Draft {
  readonly value: unknown;
  readonly requestId: string;
  readonly backend: NotebookBackend;
}

export interface UIElementModel {
  readonly valuesAtom: Atom<ReadonlyMap<string, unknown>>;
  update(id: string, value: unknown): Promise<void>;
  functionRequest(id: string): FunctionRequest | undefined;
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
  const ownedIds = new Set<string>();
  const bindings = new Map<
    string,
    {
      backend: NotebookBackend;
      notebookId: string;
      config: UIElementOutput["config"];
      controller: AbortController;
      request: FunctionRequest;
    }
  >();
  const unavailable: FunctionRequest = async () => {
    throw new Error("UI element functions are unavailable");
  };
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
        const notebook = store.get(replica.notebookAtom);
        for (const id of confirmed.keys()) {
          ownedIds.add(id);
        }
        for (const [id, binding] of bindings) {
          if (
            // Partial updates preserve config identity; full records replace it.
            confirmed.get(id)?.element.config !== binding.config ||
            backend !== binding.backend ||
            notebook?.id !== binding.notebookId ||
            !notebook.operations.includes("ui_element.send")
          ) {
            binding.controller.abort();
            bindings.delete(id);
          }
        }
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
      const unsubscribeNotebook = store.sub(replica.notebookAtom, reconcile);
      reconcile();
      signal.addEventListener(
        "abort",
        () => {
          unsubscribeRecords();
          unsubscribeBackend();
          unsubscribeNotebook();
          for (const binding of bindings.values()) {
            binding.controller.abort();
          }
          bindings.clear();
          ownedIds.clear();
          store.set(draftsAtom, new Map());
        },
        { once: true },
      );
    },
    functionRequest(id) {
      const record = store.get(replica.uiElementsAtom).get(id);
      if (!record && !ownedIds.has(id)) {
        return undefined;
      }
      const backend = store.get(replica.backendAtom);
      const notebook = store.get(replica.notebookAtom);
      if (
        !record ||
        !lifetime ||
        lifetime.aborted ||
        !backend ||
        !notebook?.operations.includes("ui_element.send")
      ) {
        return unavailable;
      }
      const existing = bindings.get(id);
      if (existing) {
        return existing.request;
      }
      const controller = new AbortController();
      const signal = AbortSignal.any([lifetime, controller.signal]);
      const send = createHostFunctionRequest(
        backend.notebook(notebook.id),
        signal,
      );
      const request: FunctionRequest = (args) => {
        if (args.namespace !== id) {
          return unavailable(args);
        }
        return send(args);
      };
      bindings.set(id, {
        backend,
        notebookId: notebook.id,
        config: record.element.config,
        controller,
        request,
      });
      return request;
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
