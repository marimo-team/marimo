/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync, readdirSync } from "node:fs";
import { Schema } from "effect";
import { expect, it } from "vitest";
import * as S from "../Schemas.ts";
import * as Host from "../Host.ts";
import * as Notebook from "../Notebook.ts";
import * as Analysis from "../experimental/Analysis.ts";

const root = new URL("../../../../protocols/host/", import.meta.url);
const fixtures = new URL("fixtures/", root);
function read(name: string): unknown {
  return JSON.parse(readFileSync(new URL(name, fixtures), "utf8"));
}

const records = {
  "record.json": S.HostRecord,
  "cell.json": S.Cell,
  "cell-withheld.json": S.Cell,
  "edit.json": S.EditRequest,
  "stale-edit-request.json": S.EditRequest,
  "edit-response.json": S.EditResponse,
  "execution-restored.json": S.Execution,
  "run-cells-request.json": S.RunRequest,
  "execute-request.json": S.ExecuteRequest,
  "input-reply-request.json": S.InputReplyRequest,
  "input-reply-response.json": S.Input,
  "interrupt-runtime-response.json": S.Runtime,
  "../experimental/analysis/fixtures/analysis.json": Analysis.Analysis,
  "../experimental/analysis/fixtures/diagnostic.json": S.Error,
};

it.each(Object.entries(records))(
  "round-trips existing JSON fixture %s",
  (name, schema: Schema.Codec<unknown, unknown>) => {
    const input = read(name);
    const decoded = Schema.decodeUnknownSync(schema)(input);
    expect(Schema.encodeSync(schema)(decoded)).toEqual(input);
  },
);

it.each(readdirSync(new URL("problems/", fixtures)))(
  "accepts existing problem %s",
  (name) => {
    const input = read(`problems/${name}`);
    const problem = Schema.decodeUnknownSync(S.Problem)(input);
    expect(Schema.encodeSync(S.Problem)(problem)).toEqual(input);
  },
);

it.each([
  ...readdirSync(fixtures).filter((name) => name.endsWith(".sse")),
  "../experimental/analysis/fixtures/notebook-events.sse",
])("decodes events from %s", (name) => {
  const text = readFileSync(new URL(name, fixtures), "utf8");
  const schema = name.startsWith("../experimental/")
    ? Analysis.NotebookEvent
    : ["events.sse", "events-reset.sse"].includes(name)
      ? Host.Event
      : Notebook.Event;
  let count = 0;
  for (const frame of text.split(/\r?\n\r?\n/)) {
    const event = /^event: (.+)$/m.exec(frame)?.[1];
    if (!event) {
      continue;
    }
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    const id = /^id: (.+)$/m.exec(frame)?.[1];
    const input = { event, data: JSON.parse(data), ...(id ? { id } : {}) };
    expect(Schema.decodeUnknownSync(schema)(input)).toEqual(input);
    count++;
  }
  expect(count).toBeGreaterThan(0);
});

it.each([
  ["2026-01-01T00:00:00Z", true],
  ["2026-01-01T00:00:00.123456+00:00", true],
  ["2026-01-01T00:00:00", false],
  ["2026-01-01", false],
])("accepts %s as a timestamp: %s", (text, valid) => {
  expect(Schema.is(S.Timestamp)(text)).toBe(valid);
});

it.each([
  [{}, false],
  [{ name: "Forecasts" }, true],
  [{ path: "forecasts.py" }, true],
])("accepts %j as a notebook update: %s", (body, valid) => {
  expect(Schema.is(S.UpdateNotebookRequest)(body)).toBe(valid);
});

it("retains nullable, omitted, arbitrary JSON, and forward-compatible field semantics", () => {
  const cell = Schema.decodeUnknownSync(S.Cell)(read("cell.json"));
  expect(
    Schema.decodeUnknownSync(S.Cell)({ ...cell, code: null, future: true }),
  ).toEqual({ ...cell, code: null });
  const { code: _code, ...missing } = cell;
  expect(() => Schema.decodeUnknownSync(S.Cell)(missing)).toThrow(
    Schema.SchemaError,
  );
  expect(() =>
    Schema.decodeUnknownSync(S.CellInput)({ id: cell.id, code: null }),
  ).toThrow(Schema.SchemaError);
  expect(Schema.decodeUnknownSync(S.SaveRequest)({})).toEqual({});
  expect(() =>
    Schema.decodeUnknownSync(S.SaveRequest)({ decisions: null }),
  ).toThrow(Schema.SchemaError);
  for (const data of [null, false, 42, "text", { nested: [1, null, false] }]) {
    expect(
      Schema.decodeUnknownSync(S.Custom)({ type: "test.event", data }),
    ).toEqual({ type: "test.event", data });
  }
  expect(() =>
    Schema.decodeUnknownSync(S.Custom)({ type: "test.event" }),
  ).toThrow(Schema.SchemaError);
  expect(
    Schema.decodeUnknownSync(S.UnknownProblem)({
      type: "future/problem",
      title: "Future",
      status: 409,
    }),
  ).toEqual({ type: "future/problem", title: "Future", status: 409 });
  expect(() =>
    Schema.decodeUnknownSync(Notebook.Event)({
      id: "1",
      event: "ready",
      data: { unexpected: 1 },
    }),
  ).toThrow(Schema.SchemaError);
});

it("enforces integer, array, and nullable attachment constraints without narrowing wire ranges", () => {
  const edit = Schema.decodeUnknownSync(S.EditResponse)(
    read("edit-response.json"),
  );
  const decode = Schema.decodeUnknownSync(S.Document);
  expect(() => decode({ ...edit.document, version: 1.5 })).toThrow(
    Schema.SchemaError,
  );
  expect(() => decode({ ...edit.document, version: 0 })).toThrow(
    Schema.SchemaError,
  );
  expect(
    decode({ ...edit.document, version: Number.MAX_SAFE_INTEGER + 1 }).version,
  ).toBe(Number.MAX_SAFE_INTEGER + 1);
  expect(() => Schema.decodeUnknownSync(S.RunRequest)({ cells: [] })).toThrow(
    Schema.SchemaError,
  );
  const attachment = {
    id: "a",
    notebook_id: "n",
    identity: null,
    name: null,
    kind: "client",
    since: "2026-01-01T00:00:00Z",
  };
  expect(Schema.decodeUnknownSync(S.Attachment)(attachment)).toEqual(
    attachment,
  );
  expect(() =>
    Schema.decodeUnknownSync(S.Attachment)({ ...attachment, identity: " " }),
  ).toThrow(Schema.SchemaError);
  expect(() =>
    Schema.decodeUnknownSync(S.Attachment)({
      ...attachment,
      name: "x".repeat(257),
    }),
  ).toThrow(Schema.SchemaError);
});

const requestCases: {
  name: string;
  schema: "RunRequest" | "ExecuteRequest";
  valid: boolean;
  body: unknown;
}[] = JSON.parse(
  readFileSync(
    new URL("conformance/cases/execution-requests.json", root),
    "utf8",
  ),
);
it.each(requestCases)("validates $schema: $name", ({ schema, body, valid }) => {
  const requestSchema: Schema.Codec<unknown> = S[schema];
  expect(
    Schema.decodeUnknownResult(requestSchema)(body)._tag === "Success",
  ).toBe(valid);
});
