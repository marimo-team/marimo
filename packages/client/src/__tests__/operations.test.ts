/* Copyright 2026 Marimo. All rights reserved. */

import NodeFs from "node:fs";
import NodeUrl from "node:url";
import { describe, expect, expectTypeOf, it } from "vitest";
import { type OperationId, operations } from "../operations.ts";
import type * as Protocol from "../protocol.ts";

const fixtures = new NodeUrl.URL(
  "../../../../protocols/host/fixtures/",
  import.meta.url,
);

function readFixture(name: string): unknown {
  return JSON.parse(
    NodeFs.readFileSync(new NodeUrl.URL(name, fixtures), "utf8"),
  );
}

describe("operations", () => {
  it("names every operation in the spec", () => {
    expectTypeOf<OperationId>().toEqualTypeOf<
      | "events"
      | "notebook.create"
      | "notebook.update"
      | "notebook.delete"
      | "notebook.events"
      | "notebook.edit"
      | "notebook.save"
      | "notebook.open"
      | "runtime.start"
      | "runtime.stop"
      | "runtime.restart"
      | "runtime.run"
      | "runtime.interrupt"
    >();
  });

  it("validates request and response bodies with the protocol schemas", () => {
    const edit = operations["notebook.edit"];
    expectTypeOf(
      edit.body.parse,
    ).returns.toEqualTypeOf<Protocol.EditRequestOutput>();
    expect(edit.body.parse(readFixture("edit.json"))).toEqual(
      readFixture("edit.json"),
    );
    expect(
      edit.responses[200].parse(readFixture("edit-response.json")),
    ).toEqual(readFixture("edit-response.json"));
    expect(
      operations["runtime.run"].body.parse(
        readFixture("run-cells-request.json"),
      ),
    ).toEqual(readFixture("run-cells-request.json"));
  });

  it("describes streams, empty responses, and required headers", () => {
    expect(operations["notebook.events"].responses[200]).toBe(
      "text/event-stream",
    );
    expect(operations["notebook.delete"].responses[204]).toBeNull();
    expect(operations["notebook.save"].headers).toEqual({
      "Idempotency-Key": true,
      "If-Match": false,
    });
    expect(operations["runtime.interrupt"].path).toBe(
      "/notebooks/{notebook_id}/runtime/runs/{run_id}",
    );
  });
});
