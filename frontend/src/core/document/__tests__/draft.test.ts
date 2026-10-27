/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  acknowledge,
  createCell,
  deleteCell,
  type Draft,
  type EditableCell,
  editCell,
  EMPTY_DRAFT,
  setOrder,
  toChanges,
  viewDocument,
} from "../draft";
import { cell, CONFIG, document, withCells } from "./fixtures";

const confirmed = document();

function edits(...steps: Parameters<typeof editCell>[3][]): Draft {
  return steps.reduce(
    (draft, edit) => editCell(confirmed, draft, "c1", edit),
    EMPTY_DRAFT,
  );
}

describe("editCell", () => {
  it("lets later fields win and merges config field by field", () => {
    const draft = edits(
      { code: "a", config: { hide_code: true } },
      { name: "n", config: { column: 1, hide_code: undefined } },
    );
    expect(viewDocument(confirmed, draft).cells.get("c1")).toEqual({
      id: "c1",
      code: "a",
      name: "n",
      config: { ...CONFIG, hide_code: true, column: 1 },
    });
  });

  it("keeps a reversal to the confirmed value as a draft", () => {
    const draft = edits({ code: "local" }, { code: "x = 1" });
    const remote = withCells(confirmed, { c1: cell("c1", "earlier edit") });
    expect(viewDocument(remote, draft).cells.get("c1")?.code).toBe("x = 1");
  });

  it("accepts empty strings, false and null while ignoring undefined", () => {
    const draft = edits(
      { code: "", config: { column: 1, disabled: true } },
      {
        code: undefined,
        config: { column: null, disabled: false, hide_code: undefined },
      },
    );
    expect(viewDocument(confirmed, draft).cells.get("c1")).toEqual({
      id: "c1",
      code: "",
      name: "_",
      config: CONFIG,
    });
  });
});

describe("createCell and deleteCell", () => {
  it("fills protocol defaults and places the cell in the view", () => {
    const atEnd = createCell(EMPTY_DRAFT, { id: "c3", code: "3" });
    const after = createCell(
      EMPTY_DRAFT,
      { id: "c3", code: "3" },
      { after: "c1" },
    );
    const before = createCell(
      EMPTY_DRAFT,
      { id: "c3", code: "3" },
      { before: "c1" },
    );
    const orphan = createCell(
      EMPTY_DRAFT,
      { id: "c3", code: "3" },
      { after: "gone" },
    );
    expect(viewDocument(confirmed, atEnd).order).toEqual(["c1", "c2", "c3"]);
    expect(viewDocument(confirmed, after).order).toEqual(["c1", "c3", "c2"]);
    expect(viewDocument(confirmed, before).order).toEqual(["c3", "c1", "c2"]);
    expect(viewDocument(confirmed, orphan).order).toEqual(["c1", "c2", "c3"]);
    expect(viewDocument(confirmed, atEnd).cells.get("c3")).toEqual({
      id: "c3",
      code: "3",
      name: "_",
      config: CONFIG,
    });
  });

  it("forgets a created cell when it is deleted", () => {
    const draft = deleteCell(
      createCell(EMPTY_DRAFT, { id: "c3", code: "" }),
      "c3",
    );
    expect(toChanges(confirmed, draft)).toEqual([]);
    expect(viewDocument(confirmed, draft).order).toEqual(["c1", "c2"]);
  });
});

describe("viewDocument", () => {
  it("preserves withheld source separately from an empty cell", () => {
    const hidden = cell("c1", "", { code: null });
    const empty = cell("c2", "");
    const source = withCells(confirmed, { c1: hidden, c2: empty });
    expect(viewDocument(source, EMPTY_DRAFT)).toEqual({
      order: ["c1", "c2"],
      cells: new Map([
        ["c1", hidden],
        ["c2", empty],
      ]),
    });
    expect(toChanges(source, EMPTY_DRAFT)).toEqual([]);
  });

  it("follows the host for untouched fields, cells and order", () => {
    const draft = edits({ code: "local", config: { hide_code: true } });
    const remote = withCells(
      confirmed,
      {
        c1: cell("c1", "remote", {
          name: "renamed",
          config: { ...CONFIG, disabled: true },
          version: 2,
        }),
        c2: cell("c2", "remote too"),
      },
      ["c2", "c1"],
    );
    expect(viewDocument(remote, draft)).toEqual({
      order: ["c2", "c1"],
      cells: new Map<string, EditableCell | undefined>([
        [
          "c1",
          {
            id: "c1",
            code: "local",
            name: "renamed",
            config: { ...CONFIG, disabled: true, hide_code: true },
          },
        ],
        ["c2", remote.cells.get("c2")],
      ]),
    });
  });
});

describe("toChanges", () => {
  it.each([{ name: "renamed" }, { config: { hide_code: true } }])(
    "withholds the whole request when an edited cell lacks source: %o",
    (edit) => {
      const hidden = withCells(confirmed, {
        c1: cell("c1", "", { code: null }),
      });
      const created = createCell(EMPTY_DRAFT, { id: "c3", code: "" });
      const draft = editCell(hidden, created, "c1", edit);
      expect(toChanges(hidden, draft)).toBeNull();
      expect(viewDocument(hidden, draft).cells.get("c1")?.code).toBeNull();
    },
  );

  it.each(["replacement", ""])(
    "uses explicitly supplied source %j when the host withholds it",
    (code) => {
      const hidden = withCells(confirmed, {
        c1: cell("c1", "", { code: null }),
      });
      const draft = editCell(hidden, EMPTY_DRAFT, "c1", {
        name: "renamed",
        code,
      });
      expect(toChanges(hidden, draft)).toEqual([
        {
          kind: "put_cell",
          base_etag: "c1-etag",
          cell: { id: "c1", code, name: "renamed", config: CONFIG },
        },
      ]);
    },
  );

  it("can delete and reorder cells without their source", () => {
    const hidden = withCells(confirmed, {
      c1: cell("c1", "", { code: null }),
      c2: cell("c2", "", { code: null }),
    });
    expect(toChanges(hidden, deleteCell(EMPTY_DRAFT, "c1"))).toEqual([
      { kind: "delete_cell", id: "c1", base_etag: "c1-etag" },
    ]);
    expect(toChanges(hidden, setOrder(EMPTY_DRAFT, ["c2", "c1"]))).toEqual([
      { kind: "set_order", base_etag: "order-1", order: ["c2", "c1"] },
    ]);
  });

  it("is empty for an empty draft and omits puts that change nothing", () => {
    expect(toChanges(confirmed, EMPTY_DRAFT)).toEqual([]);
    expect(
      toChanges(confirmed, edits({ code: "local" }, { code: "x = 1" })),
    ).toEqual([]);
  });

  it("puts the merged cell against the confirmed etag", () => {
    const draft = edits({ code: "local" });
    const remote = withCells(confirmed, {
      c1: cell("c1", "remote", { name: "renamed", etag: "c1-etag-2" }),
    });
    expect(toChanges(remote, draft)).toEqual([
      {
        kind: "put_cell",
        base_etag: "c1-etag-2",
        cell: { id: "c1", code: "local", name: "renamed", config: CONFIG },
      },
    ]);
  });

  it.each([{ after: "c3" }, { before: "c3" }])(
    "can anchor to a cell created earlier in the request: %o",
    (placement) => {
      let draft = createCell(EMPTY_DRAFT, { id: "c3", code: "3" });
      draft = createCell(draft, { id: "c4", code: "4" }, placement);
      expect(toChanges(confirmed, draft)).toEqual([
        {
          kind: "put_cell",
          base_etag: null,
          cell: { id: "c3", code: "3", name: "_", config: CONFIG },
        },
        {
          kind: "put_cell",
          base_etag: null,
          cell: { id: "c4", code: "4", name: "_", config: CONFIG },
          ...placement,
        },
      ]);
    },
  );

  it.each([{ after: "c2" }, { before: "c2" }])(
    "omits an anchor deleted earlier in the request: %o",
    (placement) => {
      let draft = deleteCell(EMPTY_DRAFT, "c2");
      draft = createCell(draft, { id: "c3", code: "3" }, placement);
      expect(toChanges(confirmed, draft)).toEqual([
        { kind: "delete_cell", id: "c2", base_etag: "c2-etag" },
        {
          kind: "put_cell",
          base_etag: null,
          cell: { id: "c3", code: "3", name: "_", config: CONFIG },
        },
      ]);
    },
  );

  it("creates, deletes, then sets the reconciled order", () => {
    let draft = setOrder(EMPTY_DRAFT, ["c2", "c1"]);
    draft = createCell(draft, { id: "c3", code: "3" }, { after: "c2" });
    draft = deleteCell(draft, "c1");
    expect(toChanges(confirmed, draft)).toEqual([
      {
        kind: "put_cell",
        base_etag: null,
        cell: { id: "c3", code: "3", name: "_", config: CONFIG },
        after: "c2",
      },
      { kind: "delete_cell", id: "c1", base_etag: "c1-etag" },
      { kind: "set_order", base_etag: "order-1", order: ["c2", "c3"] },
    ]);
  });
});

describe("acknowledge", () => {
  it("releases accepted fields independently, keeping later code and config edits", () => {
    const sent = edits({
      code: "sent",
      config: { hide_code: true, column: 1 },
    });
    const later = editCell(confirmed, sent, "c1", {
      code: "typed more",
      config: { column: 2 },
    });
    const remote = withCells(confirmed, {
      c1: cell("c1", "remote", { config: { ...CONFIG, column: 1 } }),
    });
    expect(
      viewDocument(remote, acknowledge(later, sent)).cells.get("c1"),
    ).toEqual({
      id: "c1",
      code: "typed more",
      name: "_",
      config: { ...CONFIG, column: 2 },
    });
  });

  it("turns an accepted creation into an edit of only the fields changed since", () => {
    const sent = createCell(EMPTY_DRAFT, { id: "c3", code: "3" });
    const later = editCell(confirmed, sent, "c3", { name: "named" });
    const remote = withCells(confirmed, { c3: cell("c3", "remote code") });
    expect(toChanges(remote, acknowledge(later, sent))).toEqual([
      {
        kind: "put_cell",
        base_etag: "c3-etag",
        cell: { id: "c3", code: "remote code", name: "named", config: CONFIG },
      },
    ]);
  });

  it("releases an accepted order but preserves a subsequent reorder", () => {
    const sent = setOrder(EMPTY_DRAFT, ["c2", "c1"]);
    const later = setOrder(sent, ["c1", "c2"]);
    const remote = withCells(confirmed, {}, ["c2", "c1"]);
    expect(toChanges(remote, acknowledge(sent, sent))).toEqual([]);
    expect(toChanges(remote, acknowledge(later, sent))).toEqual([
      {
        kind: "set_order",
        base_etag: remote.revision.order_etag,
        order: ["c1", "c2"],
      },
    ]);
  });
});
