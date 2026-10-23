/* Copyright 2026 Marimo. All rights reserved. */

import { atom, createStore } from "jotai/vanilla";
import { describe, expect, it, vi } from "vitest";
import type { Document } from "../../host/resources/document";
import { createDocumentModel, type DocumentSubmission } from "../model";
import { cell, document, withCells } from "./fixtures";

function setup() {
  const store = createStore();
  const source = atom<Document | null>(document());
  const model = createDocumentModel(store, source);
  return {
    store,
    source,
    ...model,
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
    "preserves later typing when the %s arrives first",
    (first) => {
      const {
        store,
        source,
        editAtom,
        cellAtom,
        changesAtom,
        submitAtom,
        submit,
        settle,
      } = setup();
      store.set(editAtom, (tx) => {
        tx.setCode("c1", "sent");
        tx.updateConfig("c1", { hide_code: true });
      });
      const sent = submit();
      store.set(editAtom, (tx) => tx.setCode("c1", "still typing"));
      const confirmed = withCells(document(), {
        c1: cell("c1", "sent", {
          etag: "accepted",
          config: { ...cell("c1", "").config, hide_code: true },
        }),
      });
      const onCell = vi.fn();
      store.sub(cellAtom("c1"), onCell);
      const arrivals = {
        response: () => settle(sent, confirmed),
        stream: () => store.set(source, confirmed),
      };
      arrivals[first]();
      expect(store.set(submitAtom)).toBeNull();
      arrivals[first === "response" ? "stream" : "response"]();
      expect(onCell).not.toHaveBeenCalled();
      expect(store.get(cellAtom("c1"))?.code).toBe("still typing");
      expect(store.get(changesAtom)).toEqual([
        {
          kind: "put_cell",
          base_etag: "accepted",
          cell: {
            id: "c1",
            code: "still typing",
            name: "_",
            config: confirmed.cells.get("c1")?.config,
          },
        },
      ]);
      const next = submit();
      settle(sent, confirmed);
      expect(store.set(submitAtom)).toBeNull();
      const updated = withCells(confirmed, {
        c1: cell("c1", "still typing", {
          config: confirmed.cells.get("c1")!.config,
        }),
      });
      settle(next, updated);
      store.set(source, updated);
      expect(store.get(changesAtom)).toEqual([]);
    },
  );

  it.each(["response", "stream"] as const)(
    "never shows a cancelled creation when the %s arrives first",
    (first) => {
      const {
        store,
        source,
        editAtom,
        cellAtom,
        orderAtom,
        changesAtom,
        submit,
        settle,
      } = setup();
      store.set(editAtom, (tx) => tx.createCell({ id: "c3", code: "new" }));
      const sent = submit();
      store.set(editAtom, (tx) => tx.deleteCell("c3"));
      const onCell = vi.fn();
      store.sub(cellAtom("c3"), onCell);
      // An unrelated revision before the creation must not forget the deletion.
      const intermediate = withCells(document(), { c2: cell("c2", "remote") });
      store.set(source, intermediate);
      const confirmed = withCells(intermediate, { c3: cell("c3", "new") });
      const arrivals = {
        response: () => settle(sent, confirmed),
        stream: () => store.set(source, confirmed),
      };
      arrivals[first]();
      arrivals[first === "response" ? "stream" : "response"]();
      expect(onCell).not.toHaveBeenCalled();
      expect(store.get(orderAtom)).toEqual(["c1", "c2"]);
      expect(store.get(changesAtom)).toEqual([
        { kind: "delete_cell", id: "c3", base_etag: "c3-etag" },
      ]);
      const deletion = submit();
      const removed = withCells(confirmed, { c3: null });
      store.set(source, removed);
      settle(deletion, removed);
      settle(sent, confirmed);
      expect(store.get(changesAtom)).toEqual([]);
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

  it.each(["before reset", "during reset", "after snapshot"] as const)(
    "confirms a submission across reset when its response arrives %s",
    (arrival) => {
      const { store, source, editAtom, cellAtom, submit, settle } = setup();
      store.set(editAtom, (tx) => tx.setCode("c1", "unsaved"));
      const sent = submit();
      const old = withCells(document(), { c1: cell("c1", "unsaved") });
      store.set(editAtom, (tx) => tx.setCode("c1", "newer typing"));
      if (arrival === "before reset") {
        settle(sent, old);
      }
      store.set(source, null);
      if (arrival === "during reset") {
        settle(sent, old);
      }
      const fresh = withCells(old, { c2: cell("c2", "unrelated") });
      store.set(source, fresh);
      if (arrival === "after snapshot") {
        settle(sent, old);
      }
      expect(store.get(cellAtom("c1"))?.code).toBe("newer typing");
      const retried = submit();
      const accepted = withCells(fresh, { c1: cell("c1", "newer typing") });
      settle(retried, accepted);
      store.set(source, accepted);
      store.set(source, withCells(accepted, { c1: cell("c1", "remote") }));
      expect(store.get(cellAtom("c1"))?.code).toBe("remote");
    },
  );

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

  it("does not treat a response for another notebook as acceptance", () => {
    const { store, editAtom, settleAtom, submitAtom, submit } = setup();
    store.set(editAtom, (tx) => tx.setCode("c1", "local"));
    const sent = submit();
    expect(() => store.set(settleAtom, sent, document("n2").revision)).toThrow(
      "another notebook",
    );
    expect(store.set(submitAtom)).toBeNull();
  });

  it("releases an unsent reversal without making a request", () => {
    const { store, source, editAtom, cellAtom, submitAtom } = setup();
    store.set(editAtom, (tx) => tx.setCode("c1", "local"));
    store.set(editAtom, (tx) => tx.setCode("c1", "x = 1"));
    expect(store.set(submitAtom)).toBeNull();
    store.set(source, withCells(document(), { c1: cell("c1", "remote") }));
    expect(store.get(cellAtom("c1"))?.code).toBe("remote");
  });

  it("stops observing and accepting work after disposal", () => {
    const {
      store,
      source,
      editAtom,
      orderAtom,
      submitAtom,
      submit,
      settle,
      dispose,
    } = setup();
    store.set(editAtom, (tx) => tx.setCode("c1", "local"));
    const sent = submit();
    dispose();
    const onOrder = vi.fn();
    store.sub(orderAtom, onOrder);
    const confirmed = withCells(document(), { c1: cell("c1", "local") });
    store.set(source, confirmed);
    settle(sent, confirmed);
    const edit = vi.fn();
    store.set(editAtom, edit);
    dispose();
    expect(edit).not.toHaveBeenCalled();
    expect(onOrder).not.toHaveBeenCalled();
    expect(store.get(orderAtom)).toBeNull();
    expect(store.set(submitAtom)).toBeNull();
  });
});
