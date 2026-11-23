/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import { Schema } from "effect";
import { describe, expect, it } from "vitest";
import { makeHostContract } from "../contract.ts";
import { defineFeature } from "../experimental/defineFeature.ts";
import { Cursor, event } from "../internal/events.ts";
import * as Host from "../Host.ts";
import * as Notebook from "../Notebook.ts";
import { Notebook as ExperimentalNotebook } from "../experimental.ts";

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
    expect(Schema.is(Host.StreamEvent)(event)).toBe(catalog);
    expect(Schema.is(Notebook.StreamEvent)(event)).toBe(notebook);
  });

  it("includes a feature event in its stream, the event union, and the kinds filter", () => {
    const catalogEvent = event("catalog.notice", Schema.String, { id: Cursor });
    const notebookEvent = event("notebook.notice", Schema.Number, {
      id: Cursor,
    });
    const contract = makeHostContract([
      defineFeature({
        catalog: { events: [catalogEvent] },
        notebook: { events: [notebookEvent] },
      }),
    ]);

    const catalog = { event: "catalog.notice", id: "1", data: "hello" };
    const notebook = { event: "notebook.notice", id: "2", data: 3 };
    for (const [input, inCatalog] of [
      [catalog, true],
      [notebook, false],
    ] as const) {
      expect(Schema.is(contract.events.CatalogStreamEvent)(input)).toBe(
        inCatalog,
      );
      expect(Schema.is(contract.events.NotebookStreamEvent)(input)).toBe(
        !inCatalog,
      );
      expect(Schema.is(contract.events.Event)(input)).toBe(true);
      expect(Schema.is(contract.events.ObjectKind)(input.event)).toBe(true);
    }
  });

  it("retains required cursors, empty control data, and custom timestamps", () => {
    const accepts = Schema.is(Notebook.StreamEvent);
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
    expect(Schema.is(Notebook.StreamEvent)(analysisEvent)).toBe(false);
    expect(Schema.is(Host.StreamEvent)(analysisEvent)).toBe(false);
    const decoded = Schema.decodeUnknownSync(ExperimentalNotebook.StreamEvent)(
      analysisEvent,
    );
    expect(
      Schema.encodeSync(ExperimentalNotebook.StreamEvent)(decoded),
    ).toEqual(analysisEvent);
    expect(
      Schema.is(ExperimentalNotebook.StreamEvent)({
        event: "analysis",
        data: {},
      }),
    ).toBe(false);
  });
});
