/* Copyright 2026 Marimo. All rights reserved. */

import { OpenApi } from "effect/http-api";
import { expect, it } from "vitest";
import * as Analysis from "../experimental/Analysis.ts";
import * as Host from "../Host.ts";

const { referencePolicy } = Host;
const stable = OpenApi.fromApi(Host.Api, { referencePolicy });
const experimental = OpenApi.fromApi(Analysis.Api, { referencePolicy });
const schemas = stable.components.schemas;

it("closes request bodies and keeps other objects open", () => {
  const closed = Object.entries(schemas)
    .filter(([, schema]) => schema.additionalProperties === false)
    .map(([name]) => name);
  expect(closed.toSorted()).toEqual([
    "CellConfigInput",
    "CellInput",
    "CreateNotebookRequest",
    "DeleteCell",
    "EditRequest",
    "ExecuteRequest",
    "InputReplyRequest",
    "PutCell",
    "RequestedCell",
    "RunRequest",
    "SaveRequest",
    "SetOrder",
    "StartRuntimeRequest",
    "UpdateNotebookRequest",
  ]);
  expect(schemas.ReadyEvent.properties).toMatchObject({
    data: { type: "object", additionalProperties: false },
  });
});

it("puts descriptions beside their schemas and names each problem", () => {
  expect(JSON.stringify(stable)).not.toContain('"allOf"');
  expect(
    Object.keys(schemas).filter((name) => name.endsWith("Encoded")),
  ).toEqual([]);
  expect(schemas.NotFoundProblem.required).toEqual(
    expect.arrayContaining(["type", "status", "title"]),
  );
  expect(schemas.NotFoundProblem.properties).toMatchObject({
    status: { type: "integer", enum: [404], default: 404 },
    title: { type: "string", default: "Not found" },
  });
  for (const [name, schema] of Object.entries(schemas)) {
    if (
      !name.endsWith("Problem") ||
      name === "Problem" ||
      name === "UnknownProblem"
    ) {
      continue;
    }
    expect(schema.properties).toMatchObject({
      status: { type: "integer", default: expect.any(Number) },
      title: { type: "string", default: expect.any(String) },
    });
  }
});

it("lists the problems each route can answer with", () => {
  const save = stable.paths["/notebooks/{notebook_id}/save"].post;
  expect(
    save?.responses[412]?.content?.["application/problem+json"]?.schema,
  ).toEqual({ $ref: "#/components/schemas/PreconditionFailedProblem" });
  expect(save?.security).toEqual([{ hostToken: [] }]);
});

it("adds experimental features without changing the stable protocol", () => {
  expect(experimental.paths).toEqual(stable.paths);
  const extended = experimental.components.schemas;
  for (const [name, schema] of Object.entries(schemas)) {
    if (name === "Event" || name === "ObjectType") {
      continue;
    }
    expect(extended[name]).toEqual(schema);
  }
  expect(new Set(extended.ObjectType.enum as string[])).toEqual(
    new Set([...(schemas.ObjectType.enum as string[]), "analysis"]),
  );
  expect(
    Object.keys(extended)
      .filter((name) => !(name in schemas))
      .toSorted(),
  ).toEqual(["Analysis", "AnalysisEvent", "AnalysisMessage", "CellAnalysis"]);
});
