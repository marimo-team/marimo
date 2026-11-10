/* Copyright 2026 Marimo. All rights reserved. */

import { expect, it } from "vitest";
import * as Analysis from "../experimental/Analysis.ts";
import * as Host from "../Host.ts";
import * as OpenApi from "../OpenApi.ts";

const stable = OpenApi.fromApi(Host.Api);
const experimental = OpenApi.fromApi(Analysis.Api);
const schemas = stable.components.schemas;

it("keeps objects open unless a schema closes itself", () => {
  const closed = Object.entries(schemas)
    .filter(([, schema]) => schema.additionalProperties === false)
    .map(([name]) => name);
  expect(closed.toSorted()).toEqual(["ExecuteRequest", "RunRequest"]);
});

it("puts descriptions beside their schemas and names each problem", () => {
  expect(JSON.stringify(stable)).not.toContain('"allOf"');
  expect(
    Object.keys(schemas).filter((name) => name.endsWith("Encoded")),
  ).toEqual([]);
  expect(schemas.NotFoundProblem.required).toEqual(
    expect.arrayContaining(["type", "status", "title"]),
  );
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
