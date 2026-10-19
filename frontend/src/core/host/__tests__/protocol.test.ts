/* Copyright 2026 Marimo. All rights reserved. */

import NodeFs from "node:fs";
import NodeUrl from "node:url";
import { describe, expect, expectTypeOf, it } from "vitest";
import type { NotificationMessage } from "../../kernel/messages";
import * as Protocol from "../protocol";

const fixtures = new NodeUrl.URL(
  "../../../../../protocols/host/fixtures/",
  import.meta.url,
);

function readFixture(name: string): unknown {
  return JSON.parse(
    NodeFs.readFileSync(new NodeUrl.URL(name, fixtures), "utf8"),
  );
}

const records = {
  "record.json": Protocol.HostRecord,
  "cell.json": Protocol.Cell,
  "analysis.json": Protocol.Analysis,
  "diagnostic.json": Protocol.Error,
  "edit.json": Protocol.EditRequest,
  "edit-conflict-request.json": Protocol.EditRequest,
  "edit-response.json": Protocol.EditResponse,
  "execution-restored.json": Protocol.Execution,
  "run-cells-request.json": Protocol.RunRequest,
};

describe("host protocol fixtures", () => {
  it.each(Object.entries(records))("parses %s unchanged", (name, schema) => {
    const input = readFixture(name);
    const original = structuredClone(input);
    expect(schema.parse(input)).toEqual(original);
    expect(input).toEqual(original);
  });

  it.each(NodeFs.readdirSync(new NodeUrl.URL("problems/", fixtures)))(
    "parses problem %s",
    (name) => {
      const input = readFixture(`problems/${name}`);
      expect(Protocol.Problem.parse(input)).toEqual(input);
    },
  );

  it.each(NodeFs.readdirSync(fixtures).filter((name) => name.endsWith(".sse")))(
    "parses events in %s unchanged",
    (name) => {
      const stream = NodeFs.readFileSync(
        new NodeUrl.URL(name, fixtures),
        "utf8",
      );
      let count = 0;
      for (const frame of stream.split(/\r?\n\r?\n/)) {
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
        const payload: unknown = JSON.parse(data);
        const input = { event, data: payload, ...(id ? { id } : {}) };
        const original = structuredClone(input);
        expect(Protocol.Event.parse(input)).toEqual(original);
        expect(input).toEqual(original);
        count += 1;
      }
      expect(count).toBeGreaterThan(0);
    },
  );
});

describe("host protocol bindings", () => {
  it("preserves native marimo message contents", () => {
    expectTypeOf<
      Protocol.MarimoEvent["data"]["marimo"]
    >().toEqualTypeOf<NotificationMessage>();
    const input = {
      event: "marimo",
      id: "42",
      data: {
        marimo: {
          op: "variables",
          variables: [{ name: "x", value: Number.NaN }],
        },
      },
    };
    expect(Protocol.Event.parse(input)).toEqual(input);
  });

  it("accepts additive fields and preserves arbitrary notebook settings", () => {
    const cell = Protocol.Cell.parse(readFixture("cell.json"));
    const input = {
      ...cell,
      future: { enabled: true },
      config: { ...cell.config, future: 42 },
    };
    const original = structuredClone(input);
    expect(Protocol.Cell.parse(input)).toEqual(cell);
    expect(input).toEqual(original);

    const { document } = Protocol.EditResponse.parse(
      readFixture("edit-response.json"),
    );
    const configured = {
      ...document,
      app_config: { extension: { values: [1, null, false] } },
    };
    expect(Protocol.Document.parse(configured)).toEqual(configured);
  });

  it("applies the defaults declared for cell inputs", () => {
    expect(
      Protocol.CellInput.parse({ id: "c3", code: "x = 1", config: {} }),
    ).toEqual({
      id: "c3",
      code: "x = 1",
      name: "_",
      config: {
        column: null,
        disabled: false,
        hide_code: false,
        expand_output: false,
      },
    });
  });

  it.each(["run_id", "runtime_id", "caused_by"] as const)(
    "requires the nullable execution field %s",
    (field) => {
      const execution = Protocol.Execution.parse(
        readFixture("execution-restored.json"),
      );
      const missing = Object.fromEntries(
        Object.entries(execution).filter(([key]) => key !== field),
      );
      expect(Protocol.Execution.safeParse(missing).success).toBe(false);
      expect(
        Protocol.Execution.safeParse({ ...execution, [field]: null }).success,
      ).toBe(true);
    },
  );

  it("preserves snapshot metadata omissions and validates live timestamps", () => {
    const cell = Protocol.Cell.parse(readFixture("cell.json"));
    expect(Protocol.CellMessage.parse({ cell })).toEqual({ cell });
    const message = { cell, time: "2026-01-01T12:00:00+05:30" };
    expect(Protocol.CellMessage.parse(message)).toEqual(message);
    for (const time of [
      null,
      "yesterday",
      "2026-02-30T12:00:00Z",
      "2026-01-01T12:00:00",
    ]) {
      expect(Protocol.CellMessage.safeParse({ cell, time }).success).toBe(
        false,
      );
    }
  });

  it("rejects invalid cell fields without coercing their values", () => {
    const cell = Protocol.Cell.parse(readFixture("cell.json"));
    for (const patch of [
      { id: "" },
      { code: 42 },
      { etag: 42 },
      { version: "2" },
      { version: 0 },
      { version: 1.5 },
      { config: { ...cell.config, disabled: "false" } },
    ]) {
      expect(Protocol.Cell.safeParse({ ...cell, ...patch }).success).toBe(
        false,
      );
    }
    const result = Protocol.Cell.safeParse({ ...cell, code: 42 });
    expect(result.success).toBe(false);
    if (result.success) {
      throw new Error("Expected an invalid cell");
    }
    expect(result.error.issues).toEqual([
      expect.objectContaining({ path: ["code"], code: "invalid_type" }),
    ]);
  });

  it("requires the fields of the selected change kind", () => {
    const change = { kind: "delete_cell", id: "c3", base_etag: "*" };
    expect(Protocol.Change.parse(change)).toEqual(change);
    expect(
      Protocol.Change.safeParse({ kind: "delete_cell", id: "c3" }).success,
    ).toBe(false);
    expect(
      Protocol.Change.safeParse({ ...change, kind: "unknown" }).success,
    ).toBe(false);
  });

  it("requires custom payloads while allowing any JSON value", () => {
    for (const data of [
      null,
      false,
      42,
      "text",
      { nested: [1, null, false] },
    ]) {
      const custom = { type: "example.event", data };
      expect(Protocol.Custom.parse(custom)).toEqual(custom);
    }
    expect(Protocol.Custom.safeParse({ type: "example.event" }).success).toBe(
      false,
    );
  });
});
