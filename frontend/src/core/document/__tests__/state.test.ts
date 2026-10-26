/* Copyright 2026 Marimo. All rights reserved. */

import { atom, createStore } from "jotai/vanilla";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Document } from "../../host/resources/document";
import {
  createDocumentState,
  type DocumentEdit,
  type DocumentEditor,
} from "../state";
import { cell, document, withCells } from "./fixtures";

const lifetimes: AbortController[] = [];
afterEach(() =>
  lifetimes.splice(0).forEach((controller) => controller.abort()),
);

function setup(initial: Document | null = document()) {
  const store = createStore();
  const source = atom(initial);
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
    abort: () => controller.abort(),
    edit: (callback: DocumentEdit) => store.set(model.editAtom, callback),
  };
}

describe("document model", () => {
  it("distinguishes unavailable changes from an unchanged document", () => {
    const { store, source, changesAtom } = setup(null);
    expect(store.get(changesAtom)).toBeNull();
    store.set(source, document());
    expect(store.get(changesAtom)).toEqual([]);
    store.set(source, null);
    expect(store.get(changesAtom)).toBeNull();
  });

  it("keeps metadata drafts while source is unavailable and follows its return", () => {
    const initial = document();
    const { store, source, cellAtom, changesAtom, edit } = setup(initial);
    edit((tx) => tx.setName("c1", "local name"));
    const hidden = withCells(initial, {
      c1: cell("c1", "", { code: null }),
    });
    store.set(source, hidden);
    expect(store.get(cellAtom("c1"))).toEqual({
      id: "c1",
      code: null,
      name: "local name",
      config: cell("c1", "").config,
    });
    expect(store.get(changesAtom)).toBeNull();

    store.set(
      source,
      withCells(hidden, {
        c1: cell("c1", "updated source", { etag: "latest" }),
      }),
    );
    expect(store.get(changesAtom)).toEqual([
      {
        kind: "put_cell",
        base_etag: "latest",
        cell: {
          id: "c1",
          code: "updated source",
          name: "local name",
          config: cell("c1", "").config,
        },
      },
    ]);
  });

  it("rebases a local order onto the latest host order and its precondition", () => {
    const { store, source, orderAtom, changesAtom, edit } = setup();
    edit((tx) => tx.setOrder(["c2", "c1"]));
    store.set(
      source,
      withCells(document(), { c3: cell("c3", "new") }, ["c1", "c3", "c2"]),
    );
    expect(store.get(orderAtom)).toEqual(["c2", "c1", "c3"]);
    expect(store.get(changesAtom)).toEqual([
      {
        kind: "set_order",
        base_etag: 'order:["c1","c3","c2"]',
        order: ["c2", "c1", "c3"],
      },
    ]);
  });

  it.each(["before", "after"] as const)(
    "appends a creation when its %s anchor was removed remotely",
    (direction) => {
      const { store, source, orderAtom, changesAtom, edit } = setup();
      edit((tx) =>
        tx.createCell({ id: "c3", code: "" }, { [direction]: "c1" }),
      );
      store.set(source, withCells(document(), { c1: null }));
      expect(store.get(orderAtom)).toEqual(["c2", "c3"]);
      expect(store.get(changesAtom)).toEqual([
        {
          kind: "put_cell",
          base_etag: null,
          cell: {
            id: "c3",
            code: "",
            name: "_",
            config: cell("c3", "").config,
          },
        },
      ]);
    },
  );

  it("publishes the visible order when an anchor is deleted later in the draft", () => {
    const { store, orderAtom, changesAtom, edit } = setup();
    edit((tx) => {
      tx.setCode("c1", "edited before creation");
      tx.createCell({ id: "c3", code: "" }, { after: "c1" });
      tx.deleteCell("c1");
    });
    expect(store.get(orderAtom)).toEqual(["c3", "c2"]);
    expect(store.get(changesAtom)).toEqual([
      { kind: "delete_cell", id: "c1", base_etag: "c1-etag" },
      {
        kind: "put_cell",
        base_etag: null,
        cell: { id: "c3", code: "", name: "_", config: cell("c3", "").config },
      },
      { kind: "set_order", base_etag: "order-1", order: ["c3", "c2"] },
    ]);
  });

  it("does not release a draft because the host caught up", () => {
    const initial = document();
    const { store, source, cellAtom, edit } = setup(initial);
    edit((tx) => tx.setCode("c1", "local"));
    for (const code of ["local", "later remote edit"]) {
      store.set(source, withCells(initial, { c1: cell("c1", code) }));
      expect(store.get(cellAtom("c1"))?.code).toBe("local");
    }
  });

  it("keeps drafts separate when notebooks reuse cell ids", () => {
    const { store, source, cellAtom, edit } = setup();
    edit((tx) => tx.setCode("c1", "first notebook"));
    store.set(source, document("n2"));
    expect(store.get(cellAtom("c1"))?.code).toBe("x = 1");
    edit((tx) => tx.setCode("c1", "second notebook"));
    store.set(source, document("n1"));
    expect(store.get(cellAtom("c1"))?.code).toBe("first notebook");
    store.set(source, document("n2"));
    expect(store.get(cellAtom("c1"))?.code).toBe("second notebook");
  });

  it("does not repeat a satisfied deletion without mounted readers", () => {
    const { store, source, cellAtom, changesAtom, edit } = setup();
    edit((tx) => {
      tx.deleteCell("c1");
      tx.setCode("c2", "keep this draft");
    });
    const removed = withCells(document(), { c1: null });
    store.set(source, removed);
    // No reads between snapshots: reconciliation must observe the removal.
    store.set(
      source,
      withCells(removed, { c1: cell("c1", "restored") }, ["c1", "c2"]),
    );
    expect(store.get(cellAtom("c1"))?.code).toBe("restored");
    expect(store.get(cellAtom("c2"))?.code).toBe("keep this draft");
    expect(store.get(changesAtom)).toEqual([
      {
        kind: "put_cell",
        base_etag: "c2-etag",
        cell: {
          id: "c2",
          code: "keep this draft",
          name: "_",
          config: cell("c2", "").config,
        },
      },
    ]);
  });

  it("retains edits when the host removes a cell and blocks partial submissions", () => {
    const { store, source, cellAtom, changesAtom, edit } = setup();
    edit((tx) => {
      tx.setCode("c1", "recover this code");
      tx.setCode("c2", "another edit");
    });
    const removed = withCells(document(), { c1: null });
    store.set(source, removed);
    expect(store.get(changesAtom)).toBeNull();
    store.set(source, withCells(removed, { c1: cell("c1", "restored") }));
    expect(store.get(cellAtom("c1"))?.code).toBe("recover this code");
    expect(store.get(changesAtom)).toHaveLength(2);
  });

  it("composes creation, field edits, deletion and order in one publication", () => {
    const { store, cellAtom, orderAtom, edit } = setup();
    const onOrder = vi.fn(() => {
      expect(store.get(cellAtom("c3"))).toEqual({
        id: "c3",
        code: "updated",
        name: "example",
        config: { ...cell("c3", "").config, hide_code: true },
      });
      expect(store.get(cellAtom("c1"))).toBeUndefined();
    });
    const unsubscribeOrder = store.sub(orderAtom, onOrder);
    edit((tx) => {
      tx.createCell({ id: "c3", code: "3" }, { after: "c2" });
      tx.setCode("c3", "updated");
      tx.setName("c3", "example");
      tx.updateConfig("c3", { hide_code: true });
      tx.deleteCell("c1");
      tx.setOrder(["c3", "c2"]);
      expect(store.get(orderAtom)).toEqual(["c1", "c2"]);
      expect(store.get(cellAtom("c3"))).toBeUndefined();
    });
    expect(store.get(orderAtom)).toEqual(["c3", "c2"]);
    expect(onOrder).toHaveBeenCalledOnce();
    unsubscribeOrder();
  });

  it("does not notify subscribers for edits that change nothing", () => {
    const { store, cellAtom, orderAtom, edit } = setup();
    const onCell = vi.fn();
    const onOrder = vi.fn();
    const unsubscribeCell = store.sub(cellAtom("c1"), onCell);
    const unsubscribeOrder = store.sub(orderAtom, onOrder);
    edit((tx) => {
      tx.setCode("c1", "x = 1");
      tx.updateConfig("c1", { column: null });
    });
    expect(onCell).not.toHaveBeenCalled();
    edit((tx) => tx.setCode("c1", "local"));
    edit((tx) => tx.setCode("c1", "local"));
    edit((tx) => tx.setOrder(["c1", "c2"]));
    expect(onCell).toHaveBeenCalledOnce();
    expect(onOrder).not.toHaveBeenCalled();
    unsubscribeCell();
    unsubscribeOrder();
  });

  it("isolates cell, order and configuration subscriptions across local and host updates", () => {
    const initial = document();
    const { store, source, cellAtom, orderAtom, appConfigAtom, edit } =
      setup(initial);
    edit((tx) => {
      tx.setCode("c1", "local");
      tx.createCell({ id: "c3", code: "new" });
    });
    const c1 = cellAtom("c1");
    const first = store.get(c1);
    const order = store.get(orderAtom);
    const config = store.get(appConfigAtom);
    const onFirst = vi.fn();
    const onSecond = vi.fn();
    const onOrder = vi.fn();
    const onConfig = vi.fn();
    const unsubscribe = [
      store.sub(c1, onFirst),
      store.sub(cellAtom("c2"), onSecond),
      store.sub(orderAtom, onOrder),
      store.sub(appConfigAtom, onConfig),
    ];

    edit((tx) => tx.setCode("c2", "other local"));
    const remote = withCells(initial, {
      c1: cell("c1", "remote", { version: 2, etag: "new-etag" }),
    });
    store.set(source, {
      ...remote,
      revision: {
        ...remote.revision,
        order: [...initial.revision.order],
        app_config: { ...initial.revision.app_config },
      },
    });
    expect(store.get(c1)).toBe(first);
    expect(store.get(orderAtom)).toBe(order);
    expect(store.get(appConfigAtom)).toBe(config);
    expect(onFirst).not.toHaveBeenCalled();
    expect(onSecond).toHaveBeenCalledOnce();
    expect(onOrder).not.toHaveBeenCalled();
    expect(onConfig).not.toHaveBeenCalled();

    store.set(
      source,
      withCells(remote, {
        c1: cell("c1", "remote", { name: "renamed" }),
      }),
    );
    expect(store.get(cellAtom("c1"))).toEqual({
      id: "c1",
      code: "local",
      name: "renamed",
      config: cell("c1", "").config,
    });
    expect(onFirst).toHaveBeenCalledOnce();
    edit((tx) => tx.setOrder(["c3", "c2", "c1"]));
    expect(onOrder).toHaveBeenCalledOnce();
    expect(onFirst).toHaveBeenCalledOnce();
    store.set(source, {
      ...remote,
      revision: { ...remote.revision, app_config: { width: "full" } },
    });
    expect(onConfig).toHaveBeenCalledOnce();
    unsubscribe.forEach((fn) => fn());
  });

  it.each([
    [
      "a missing placement anchor",
      (tx: DocumentEditor) =>
        tx.createCell({ id: "c3", code: "" }, { after: "missing" }),
      "Cell missing does not exist",
    ],
    [
      "a deleted placement anchor",
      (tx: DocumentEditor) => {
        tx.deleteCell("c2");
        tx.createCell({ id: "c3", code: "" }, { before: "c2" });
      },
      "Cell c2 does not exist",
    ],
    [
      "an exception",
      () => {
        throw new Error("failed");
      },
      "failed",
    ],
    [
      "a missing cell",
      (tx: DocumentEditor) => tx.setCode("missing", "code"),
      "Cell missing does not exist",
    ],
    [
      "a deleted cell",
      (tx: DocumentEditor) => {
        tx.deleteCell("c2");
        tx.setName("c2", "missing");
      },
      "Cell c2 does not exist",
    ],
    [
      "a duplicate cell",
      (tx: DocumentEditor) => tx.createCell({ id: "c1", code: "duplicate" }),
      "Cell c1 already exists",
    ],
    [
      "an incomplete order",
      (tx: DocumentEditor) => tx.setOrder(["c1"]),
      "Cell order must contain every cell exactly once",
    ],
    [
      "a duplicate in the order",
      (tx: DocumentEditor) => tx.setOrder(["c1", "c1"]),
      "Cell order must contain every cell exactly once",
    ],
    [
      "an unknown cell in the order",
      (tx: DocumentEditor) => tx.setOrder(["c1", "missing"]),
      "Cell order must contain every cell exactly once",
    ],
    [
      "an invalid config",
      (tx: DocumentEditor) => tx.updateConfig("c2", { column: 0.5 }),
      "Invalid input",
    ],
  ])("rolls back the whole transaction for %s", (_, fail, message) => {
    const { store, changesAtom, cellAtom, edit } = setup();
    const onChange = vi.fn();
    const unsubscribe = store.sub(cellAtom("c1"), onChange);
    expect(() =>
      edit((tx) => {
        tx.setCode("c1", "not committed");
        fail(tx);
      }),
    ).toThrow(message);
    expect(store.get(changesAtom)).toEqual([]);
    expect(onChange).not.toHaveBeenCalled();
    edit((tx) => tx.setCode("c1", "next transaction"));
    expect(store.get(cellAtom("c1"))?.code).toBe("next transaction");
    unsubscribe();
  });

  it("expires the editor after a transaction", () => {
    const { store, cellAtom, edit } = setup();
    let saved: DocumentEditor | undefined;
    edit((tx) => {
      saved = tx;
      tx.setCode("c1", "committed");
    });
    expect(() => saved?.setCode("c1", "too late")).toThrow("has ended");
    expect(store.get(cellAtom("c1"))?.code).toBe("committed");
  });

  it("rejects asynchronous transactions without publishing before or after await", async () => {
    const { store, changesAtom, edit } = setup();
    expect(() =>
      edit(async (tx) => {
        tx.setCode("c1", "before await");
        await Promise.resolve();
        tx.setCode("c1", "after await");
      }),
    ).toThrow("must be synchronous");
    await Promise.resolve();
    expect(store.get(changesAtom)).toEqual([]);
  });

  it("rejects nested transactions without overwriting drafts", () => {
    const { store, changesAtom, edit } = setup();
    expect(() =>
      edit((tx) => {
        tx.setCode("c1", "outer");
        edit((inner) => inner.setCode("c2", "inner"));
      }),
    ).toThrow("cannot be nested");
    expect(store.get(changesAtom)).toEqual([]);
  });

  it("does not commit against a source replaced during the callback", () => {
    const { store, source, changesAtom, edit } = setup();
    expect(() =>
      edit((tx) => {
        tx.setCode("c1", "old notebook");
        store.set(source, document("n2"));
      }),
    ).toThrow("changed during the transaction");
    expect(store.get(changesAtom)).toEqual([]);
    store.set(source, document());
    expect(store.get(changesAtom)).toEqual([]);
  });
});
