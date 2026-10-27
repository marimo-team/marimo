/* Copyright 2026 Marimo. All rights reserved. */

import { atom, createStore } from "jotai/vanilla";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Document } from "../../host/resources/document";
import { selectCell } from "../select";
import { createDocumentState, type DocumentSubmission } from "../state";
import { cell, document, withCells } from "./fixtures";

const lifetimes: AbortController[] = [];
afterEach(() =>
  lifetimes.splice(0).forEach((controller) => controller.abort()),
);

function setup() {
  const store = createStore();
  const source = atom<Document | null>(document());
  const controller = new AbortController();
  lifetimes.push(controller);
  const model = createDocumentState({
    store,
    source,
    signal: controller.signal,
  });
  return {
    store,
    source,
    ...model,
    cellAtom: (id: string) => selectCell(model.documentAtom, id),
    submit() {
      const submission = store.set(model.submitAtom);
      if (submission === null) {
        throw new Error("Expected a submission");
      }
      return submission;
    },
    settle(submission: DocumentSubmission, confirmed: Document) {
      store.set(model.settleAtom, submission, confirmed.revision);
    },
  };
}

describe("document submissions", () => {
  it.each(["host source", "replacement code"] as const)(
    "retains an unsendable draft until it receives %s",
    (recovery) => {
      const {
        store,
        source,
        editAtom,
        changesAtom,
        submitAtom,
        submit,
        settle,
      } = setup();
      const hidden = withCells(document(), {
        c1: cell("c1", "", { code: null }),
      });
      store.set(source, hidden);
      store.set(editAtom, (tx) => {
        tx.setCode("c2", "other edit");
        tx.setName("c1", "renamed");
      });
      expect(store.get(changesAtom)).toBeNull();
      expect(store.set(submitAtom)).toBeNull();
      expect(store.set(submitAtom)).toBeNull();

      const code = recovery === "host source" ? "revealed" : "";
      if (recovery === "host source") {
        store.set(source, withCells(hidden, { c1: cell("c1", code) }));
      } else {
        store.set(editAtom, (tx) => tx.setCode("c1", code));
      }
      const sent = submit();
      expect(sent.changes).toEqual([
        {
          kind: "put_cell",
          base_etag: "c2-etag",
          cell: {
            id: "c2",
            code: "other edit",
            name: "_",
            config: cell("c2", "").config,
          },
        },
        {
          kind: "put_cell",
          base_etag: "c1-etag",
          cell: {
            id: "c1",
            code,
            name: "renamed",
            config: cell("c1", "").config,
          },
        },
      ]);
      const accepted = withCells(store.get(source)!, {
        c1: cell("c1", code, { name: "renamed" }),
        c2: cell("c2", "other edit"),
      });
      settle(sent, accepted);
      store.set(source, accepted);
      expect(store.get(changesAtom)).toEqual([]);
    },
  );

  it.each(["response", "stream"] as const)(
    "does not notify cell subscribers when the %s acknowledges a superseded draft",
    (first) => {
      const { store, source, editAtom, cellAtom, submit, settle } = setup();
      store.set(editAtom, (tx) => {
        tx.setCode("c1", "sent");
        tx.createCell({ id: "c3", code: "new" });
      });
      const sent = submit();
      store.set(editAtom, (tx) => {
        tx.setCode("c1", "still typing");
        tx.deleteCell("c3");
      });
      const onCode = vi.fn();
      const onCreation = vi.fn();
      const unsubscribeCode = store.sub(cellAtom("c1"), onCode);
      const unsubscribeCreation = store.sub(cellAtom("c3"), onCreation);
      const confirmed = withCells(document(), {
        c1: cell("c1", "sent", { etag: "accepted", version: 2 }),
        c3: cell("c3", "new"),
      });
      const arrivals = {
        response: () => settle(sent, confirmed),
        stream: () => store.set(source, confirmed),
      };
      try {
        arrivals[first]();
        arrivals[first === "response" ? "stream" : "response"]();
        expect(onCode).not.toHaveBeenCalled();
        expect(onCreation).not.toHaveBeenCalled();
      } finally {
        unsubscribeCode();
        unsubscribeCreation();
      }
    },
  );

  it("waits for the response's later revision and follows subsequent host edits", () => {
    const { store, source, editAtom, cellAtom, submitAtom, submit, settle } =
      setup();
    store.set(editAtom, (tx) => tx.setCode("c1", "sent"));
    const sent = submit();
    const edited = withCells(document(), { c1: cell("c1", "sent") });
    const response = withCells(edited, { c2: cell("c2", "mirrored update") });
    settle(sent, response);
    store.set(source, edited);
    expect(store.set(submitAtom)).toBeNull();
    const later = withCells(response, {
      c1: cell("c1", "another client's edit"),
    });
    const seen: (string | null | undefined)[] = [];
    store.sub(cellAtom("c1"), () => seen.push(store.get(cellAtom("c1"))?.code));
    store.set(source, later);
    expect(seen).toEqual(["another client's edit"]);
    expect(store.set(submitAtom)).toBeNull();
  });

  it("invalidates submissions when switching notebooks, retaining each draft", () => {
    const { store, source, editAtom, cellAtom, submit, settle } = setup();
    store.set(editAtom, (tx) => tx.setCode("c1", "first"));
    const sent = submit();
    store.set(source, document("n2"));
    store.set(editAtom, (tx) => tx.setCode("c1", "second"));
    store.set(source, withCells(document(), { c2: cell("c2", "remote") }));
    settle(sent, withCells(document(), { c1: cell("c1", "first") }));
    expect(store.get(cellAtom("c1"))?.code).toBe("first");
    store.set(source, document("n2"));
    expect(store.get(cellAtom("c1"))?.code).toBe("second");
  });

  it("retries a rejected edit with fresh preconditions and ignores its late reply", () => {
    const { store, source, editAtom, settleAtom, submitAtom, submit, settle } =
      setup();
    store.set(editAtom, (tx) => tx.setCode("c1", "local"));
    const sent = submit();
    store.set(settleAtom, sent, null);
    const remote = withCells(document(), {
      c1: cell("c1", "remote", { name: "renamed", etag: "fresh" }),
    });
    store.set(source, remote);
    const retry = submit();
    expect(retry.changes).toEqual([
      {
        kind: "put_cell",
        base_etag: "fresh",
        cell: {
          id: "c1",
          code: "local",
          name: "renamed",
          config: cell("c1", "").config,
        },
      },
    ]);
    settle(sent, remote);
    expect(store.set(submitAtom)).toBeNull();
  });
});
