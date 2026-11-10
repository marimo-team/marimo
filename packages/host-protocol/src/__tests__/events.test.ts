/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import { Schema } from "effect";
import { describe, expect, it } from "vitest";
import * as Host from "../Host.ts";
import * as Notebook from "../Notebook.ts";
import * as Analysis from "../experimental/Analysis.ts";

const fixtures = new URL("../../../../protocols/host/", import.meta.url);
const cell: unknown = JSON.parse(
  readFileSync(new URL("fixtures/cell.json", fixtures), "utf8"),
);
const analysis: unknown = JSON.parse(
  readFileSync(
    new URL("experimental/analysis/fixtures/analysis.json", fixtures),
    "utf8",
  ),
);
const analysisEvent = { event: "analysis", data: { analysis } };

describe("scoped events", () => {
  it.each([
    [{ event: "host", data: { host: { operations: [] } } }, true, false],
    [{ event: "project.removed", data: { id: "p" } }, true, false],
    [{ event: "cell", data: { cell } }, false, true],
    [{ event: "cell.removed", data: { id: "c" } }, false, true],
    [{ event: "notebook.removed", data: { id: "n" } }, true, true],
    [{ event: "ready", id: "1", data: {} }, true, true],
    [{ event: "reset", data: {} }, true, true],
    [{ event: "future", data: {} }, false, false],
    [analysisEvent, false, false],
  ])("decodes %j only in its scope", (event, catalog, notebook) => {
    expect(Schema.is(Host.Event)(event)).toBe(catalog);
    expect(Schema.is(Notebook.Event)(event)).toBe(notebook);
  });

  it("retains required cursors, empty control data, and custom timestamps", () => {
    const accepts = Schema.is(Notebook.Event);
    expect(accepts({ event: "ready", data: {} })).toBe(false);
    expect(accepts({ event: "ready", id: "", data: {} })).toBe(false);
    expect(
      accepts({ event: "ready", id: "1", data: { unexpected: true } }),
    ).toBe(false);
    const custom = { custom: { type: "example", data: null } };
    expect(accepts({ event: "custom", data: custom })).toBe(false);
    expect(
      accepts({
        event: "custom",
        data: { ...custom, time: "2026-01-01T00:00:00Z" },
      }),
    ).toBe(true);
  });

  it("opts into analysis without widening stable streams", () => {
    expect(Schema.is(Notebook.Event)(analysisEvent)).toBe(false);
    expect(Schema.is(Host.Event)(analysisEvent)).toBe(false);
    const decoded = Schema.decodeUnknownSync(Analysis.NotebookEvent)(
      analysisEvent,
    );
    expect(Schema.encodeSync(Analysis.NotebookEvent)(decoded)).toEqual(
      analysisEvent,
    );
    expect(
      Schema.is(Analysis.NotebookEvent)({ event: "analysis", data: {} }),
    ).toBe(false);
  });
});
