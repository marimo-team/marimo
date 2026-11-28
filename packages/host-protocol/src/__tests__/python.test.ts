/* Copyright 2026 Marimo. All rights reserved. */

import { OpenApi } from "effect/http-api";
import { expect, it } from "vitest";
import * as Host from "../Host.ts";
import { events } from "../../scripts/python/events.ts";
import { models } from "../../scripts/python/models.ts";

const options = { command: "make codegen" };
const component = (name: string) => ({ $ref: `#/components/schemas/${name}` });
const written = (schemas: Record<string, unknown>) =>
  models({ components: { schemas } }, options);

it("writes an object as a frozen struct with required fields first", () => {
  const source = written({
    Cell: {
      type: "object",
      properties: {
        name: { type: "string", default: "_" },
        code: { type: "string", description: "The source." },
        column: { anyOf: [{ type: "integer" }, { type: "null" }] },
        tags: { type: "array", items: { type: "string" } },
      },
      required: ["code"],
    },
  });
  expect(source).toContain(
    [
      "class Cell(Struct, frozen=True):",
      '    code: Annotated[str, Meta(description="The source.")]',
      "    column: int | UnsetType | None = UNSET",
      '    name: str | UnsetType = "_"',
      "    tags: tuple[str, ...] | UnsetType = UNSET",
    ].join("\n"),
  );
});

it("rejects unknown members only where the schema is closed", () => {
  const source = written({
    Request: {
      type: "object",
      properties: { code: { type: "string" } },
      required: ["code"],
      additionalProperties: false,
    },
  });
  expect(source).toContain(
    "class Request(Struct, frozen=True, forbid_unknown_fields=True):",
  );
});

it("tags the members of a union by the field that tells them apart", () => {
  const state = (status: string) => ({
    type: "object",
    properties: { status: { type: "string", enum: [status] } },
    required: ["status"],
  });
  const source = written({
    Ready: state("ready"),
    Ended: state("ended"),
    State: { anyOf: [component("Ready"), component("Ended")] },
  });
  expect(source).toContain(
    'class Ready(Struct, frozen=True, tag_field="status", tag="ready"):\n    pass',
  );
  // The union is defined after the structs it names.
  expect(source.indexOf("State: TypeAlias = Ready | Ended")).toBeGreaterThan(
    source.indexOf("class Ready"),
  );
});

it("refuses a union whose members no single field tells apart", () => {
  const plain = { type: "object", properties: { id: { type: "string" } } };
  expect(() =>
    written({
      A: plain,
      B: plain,
      Either: { anyOf: [component("A"), component("B")] },
    }),
  ).toThrow("Expected one field to tell A, B apart, found 0");
});

it("gives a problem its status and title as defaults", () => {
  const source = written({
    ConflictProblem: {
      type: "object",
      properties: {
        type: { type: "string", enum: ["urn:marimo:problem:conflict"] },
        status: { type: "integer", enum: [409], default: 409 },
        title: { type: "string", default: "Conflict" },
      },
      required: ["type", "status", "title"],
    },
  });
  expect(source).toContain(
    [
      "class ConflictProblem(Struct, frozen=True):",
      '    type: Literal["urn:marimo:problem:conflict"]',
      "    status: Literal[409] = 409",
      '    title: str = "Conflict"',
    ].join("\n"),
  );
});

it("keeps each kind of id distinct from a plain string", () => {
  const source = written({
    CellId: { type: "string", minLength: 1, description: "Identifies a cell." },
    Status: { type: "string", enum: ["ready", "ended"] },
    Timestamp: { type: "string", format: "date-time" },
  });
  expect(source).toContain('    CellId = NewType("CellId", str)');
  expect(source).toContain(
    'CellId = NewType("CellId", Annotated[str, Meta(description="Identifies a cell.", min_length=1)])',
  );
  expect(source).toContain('Status: TypeAlias = Literal["ready", "ended"]');
  expect(source).toContain("Timestamp: TypeAlias = datetime");
});

it("writes adapters from schema references, whatever the schemas are called", () => {
  const document = structuredClone(
    OpenApi.fromApi(Host.Api, { referencePolicy: Host.referencePolicy }),
  ) as unknown as {
    components: { schemas: Record<string, any> };
  };
  const { schemas } = document.components;
  // Rename the project's message and event, and the field that carries it.
  const message = schemas.ProjectMessage;
  delete schemas.ProjectMessage;
  message.properties.workspace = message.properties.project;
  delete message.properties.project;
  message.required = ["workspace"];
  schemas.WorkspaceUpdate = message;
  const event = schemas.ProjectEvent;
  delete schemas.ProjectEvent;
  event.properties.data = component("WorkspaceUpdate");
  schemas.WorkspaceChanged = event;
  schemas.Event.anyOf = schemas.Event.anyOf.map((member: { $ref: string }) =>
    member.$ref.endsWith("/ProjectEvent")
      ? component("WorkspaceChanged")
      : member,
  );

  const source = events(document, options);
  expect(source).toContain(
    "            return protocol.WorkspaceChanged(\n                protocol.WorkspaceUpdate(workspace=value, request_id=request_id, time=time)",
  );
  expect(source).toContain(
    "        case protocol.WorkspaceChanged(data=data):\n            return data.workspace",
  );
  expect(source).toContain(
    "protocol.RemovedMessage(id=object_id, request_id=request_id, time=time)",
  );
});
