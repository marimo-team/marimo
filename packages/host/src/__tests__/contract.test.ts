/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync, readdirSync } from "node:fs";
import { Schema } from "effect";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import * as Protocol from "../models.ts";
import { protocolModels, toOpenApi } from "../openapi.ts";

const root = new URL("../../../../protocols/host/", import.meta.url);
interface ReferenceSchema {
  required?: string[];
  properties?: Record<string, unknown>;
  discriminator?: { mapping: Record<string, string> };
}
const reference = parse(
  readFileSync(new URL("openapi.yaml", root), "utf8"),
) as {
  components: { schemas: Record<string, ReferenceSchema> };
  paths: Record<
    string,
    Record<string, { operationId: string; responses: Record<string, unknown> }>
  >;
};
const fixtures = {
  "record.json": Protocol.HostRecord,
  "cell.json": Protocol.Cell,
  "cell-withheld.json": Protocol.Cell,
  "edit.json": Protocol.EditRequest,
  "edit-conflict-request.json": Protocol.EditRequest,
  "edit-response.json": Protocol.EditResponse,
  "execution-restored.json": Protocol.Execution,
  "run-cells-request.json": Protocol.RunRequest,
  "input-reply-request.json": Protocol.InputReplyRequest,
  "input-reply-response.json": Protocol.Input,
};
function frames(text: string) {
  return text.split(/\r?\n\r?\n/).flatMap((frame) => {
    const lines = frame.split(/\r?\n/);
    const value = (key: string) =>
      lines
        .filter((line) => line.startsWith(`${key}:`))
        .map((line) => line.slice(key.length + 1).replace(/^ /, ""));
    const data = value("data");
    if (data.length === 0) return [];
    const [event] = value("event");
    const [id] = value("id");
    return [
      {
        event,
        ...(id === undefined ? {} : { id }),
        data: JSON.parse(data.join("\n")) as unknown,
      },
    ];
  });
}

describe("protocol compatibility", () => {
  it("covers every stable model, field, required field, event, and operation", () => {
    const spec = toOpenApi();
    for (const [name, schema] of Object.entries(reference.components.schemas)) {
      const actual = spec.components.schemas[name];
      expect(actual, name).toBeDefined();
      expect(
        Object.keys(actual.properties ?? {}).sort(),
        `${name} fields`,
      ).toEqual(Object.keys(schema.properties ?? {}).sort());
      expect(
        [...((actual.required as string[]) ?? [])].sort(),
        `${name} required`,
      ).toEqual([...(schema.required ?? [])].sort());
    }
    expect(spec.components.schemas.Event.discriminator).toEqual({
      propertyName: "event",
      mapping: reference.components.schemas.Event.discriminator!.mapping,
    });
    for (const [path, methods] of Object.entries(reference.paths))
      for (const [method, operation] of Object.entries(methods)) {
        const actual = spec.paths[path][method as "get"];
        expect(actual?.operationId).toBe(operation.operationId);
        expect(Object.keys(actual!.responses)).toEqual(
          expect.arrayContaining(Object.keys(operation.responses)),
        );
      }
    expect(Object.keys(spec.paths).sort()).toEqual(
      Object.keys(reference.paths).sort(),
    );
  });
  it.each(Object.entries(fixtures))(
    "decodes the existing %s fixture",
    (name, schema) => {
      const input: unknown = JSON.parse(
        readFileSync(new URL(`fixtures/${name}`, root), "utf8"),
      );
      expect(Schema.decodeUnknownSync(schema)(input)).toEqual(input);
    },
  );
  it.each(readdirSync(new URL("fixtures/problems/", root)))(
    "decodes problem %s",
    (name) => {
      const input: unknown = JSON.parse(
        readFileSync(new URL(`fixtures/problems/${name}`, root), "utf8"),
      );
      expect(Schema.decodeUnknownSync(Protocol.Problem)(input)).toEqual(input);
    },
  );
  it.each(
    readdirSync(new URL("fixtures/", root)).filter((name) =>
      name.endsWith(".sse"),
    ),
  )("decodes stream %s", (name) => {
    const known = reference.components.schemas.Event.discriminator!.mapping;
    for (const frame of frames(
      readFileSync(new URL(`fixtures/${name}`, root), "utf8"),
    )) {
      if (frame.event && Object.hasOwn(known, frame.event))
        expect(Schema.decodeUnknownSync(Protocol.Event)(frame)).toEqual(frame);
    }
  });
  it("includes analysis only when selected and decodes its fixtures", () => {
    expect(toOpenApi().components.schemas).not.toHaveProperty("Analysis");
    expect(protocolModels()).not.toHaveProperty("Analysis");
    const spec = toOpenApi({ analysis: true });
    expect(spec.components.schemas).toHaveProperty("Analysis");
    const mapping = spec.components.schemas.Event.discriminator as {
      mapping: Record<string, string>;
    };
    expect(mapping.mapping.analysis).toBe("#/components/schemas/AnalysisEvent");
    const base = new URL("experimental/analysis/fixtures/", root);
    expect(() =>
      Schema.decodeUnknownSync(Protocol.Analysis)(
        JSON.parse(readFileSync(new URL("analysis.json", base), "utf8")),
      ),
    ).not.toThrow();
    expect(() =>
      Schema.decodeUnknownSync(Protocol.Diagnostic)(
        JSON.parse(readFileSync(new URL("diagnostic.json", base), "utf8")),
      ),
    ).not.toThrow();
    for (const frame of frames(
      readFileSync(new URL("notebook-events.sse", base), "utf8"),
    ))
      expect(
        Schema.decodeUnknownSync(Protocol.AnalysisProtocolEvent)(frame),
      ).toEqual(frame);
  });
  it("exports canonical model names, valid references, and no serialized tags", () => {
    const spec = toOpenApi({ analysis: true });
    expect(
      Object.keys(spec.components.schemas).filter((name) => /_\d+$/.test(name)),
    ).toEqual([]);
    const serialized = JSON.stringify(spec);
    for (const [, name] of serialized.matchAll(
      /"\$ref":"#\/components\/schemas\/([^"/]+)"/g,
    ))
      expect(spec.components.schemas, name).toHaveProperty(name);
    expect(serialized).not.toContain('"_tag"');
    expect(spec.components.schemas.NotebookId).toHaveProperty("type", "string");
    expect(spec.components.schemas.RunId).toHaveProperty("type", "string");
  });
  it("rejects invalid dates, ambiguous mutations, and SSE cursor injection", () => {
    expect(() =>
      Schema.decodeUnknownSync(Protocol.Timestamp)("2026-02-30T00:00:00Z"),
    ).toThrow();
    expect(
      Schema.decodeUnknownSync(Protocol.Timestamp)("2024-02-29T12:30:00+05:30"),
    ).toBe("2024-02-29T12:30:00+05:30");
    expect(() =>
      Schema.decodeUnknownSync(Protocol.UpdateNotebookRequest)({}),
    ).toThrow();
    expect(() => Schema.decodeUnknownSync(Protocol.RunRequest)({})).toThrow();
    expect(() =>
      Schema.decodeUnknownSync(Protocol.RunRequest)({
        code: "1",
        cells: [{ id: "a" }],
      }),
    ).toThrow();
    expect(() =>
      Schema.decodeUnknownSync(Protocol.PutCell)({
        kind: "put_cell",
        base_etag: null,
        cell: { id: "a", code: "1" },
        before: "b",
        after: "c",
      }),
    ).toThrow();
    expect(() =>
      Schema.decodeUnknownSync(Protocol.ReadyEvent)({
        event: "ready",
        id: "1\nevent: injected",
        data: {},
      }),
    ).toThrow();
  });
});
