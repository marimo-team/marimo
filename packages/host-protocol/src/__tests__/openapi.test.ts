/* Copyright 2026 Marimo. All rights reserved. */

import { type HttpApiClient, HttpApiEndpoint, OpenApi } from "effect/http-api";
import { expect, expectTypeOf, it } from "vitest";
import { Host as ExperimentalHost } from "../experimental.ts";
import analysis from "../experimental/features/analysis.ts";
import * as Host from "../Host.ts";
import * as P from "../api/Parameters.ts";
import * as S from "../Schemas.ts";
import { makeHostContract } from "../contract.ts";
import { defineFeature } from "../experimental/defineFeature.ts";

const { referencePolicy } = Host;
const stable = OpenApi.fromApi(Host.Api, { referencePolicy });
const experimental = OpenApi.fromApi(ExperimentalHost.Api, { referencePolicy });
const schemas = stable.components.schemas;

it("closes request bodies and keeps other objects open", () => {
  const closed = Object.entries(schemas)
    .filter(([, schema]) => schema.additionalProperties === false)
    .map(([name]) => name);
  expect(closed.toSorted()).toEqual([
    "CellConfigInput",
    "CellInput",
    "CreateCell",
    "CreateNotebookRequest",
    "DeleteCell",
    "EditRequest",
    "ExecuteRequest",
    "InputReplyRequest",
    "ReplaceCell",
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
  expect(experimental.paths).toMatchObject(stable.paths);
  const extended = experimental.components.schemas;
  const unions = ["Event", "CatalogStreamEvent", "NotebookStreamEvent"];
  for (const name of unions) {
    expect(extended[name].anyOf).toEqual(
      expect.arrayContaining(schemas[name].anyOf as unknown[]),
    );
  }
  expect(extended.ObjectKind.enum).toEqual(
    expect.arrayContaining(schemas.ObjectKind.enum as string[]),
  );
  for (const [name, schema] of Object.entries(schemas)) {
    if (unions.includes(name) || name === "ObjectKind") {
      continue;
    }
    expect(extended[name]).toEqual(schema);
  }
  expect(schemas).not.toHaveProperty("Analysis");
  expect(extended.ObjectKind.enum).toContain("analysis");
  expect(extended.NotebookStreamEvent.anyOf).toContainEqual({
    $ref: "#/components/schemas/AnalysisEvent",
  });
});

it("rejects overlapping object events and ambiguous record adapters", () => {
  const [object] = analysis.objects;
  const withKind = (kind: string) =>
    defineFeature({ objects: [{ ...object, kind }] });
  expect(() => makeHostContract([analysis, analysis])).toThrow(
    "Duplicate event name: analysis",
  );
  expect(() => makeHostContract([withKind("project.removed")])).toThrow(
    "Duplicate event name: project.removed",
  );
  expect(() => makeHostContract([analysis, withKind("mirror")])).toThrow(
    "analysis and mirror share a payload schema",
  );
});

it("rejects endpoint names already used in the same group", () => {
  const preview = HttpApiEndpoint.get("preview", "/preview");
  const feature = defineFeature({ notebook: { endpoints: [preview] } });
  expect(() => makeHostContract([feature, feature])).toThrow(
    "Duplicate endpoint: Notebook.preview",
  );
  const events = HttpApiEndpoint.get("events", "/other");
  expect(() =>
    makeHostContract([defineFeature({ catalog: { endpoints: [events] } })]),
  ).toThrow("Duplicate endpoint: Host.events");
});

it("composes an endpoint-only feature alongside analysis", () => {
  const emit = HttpApiEndpoint.post("emit", "/notebooks/:notebook_id/emit", {
    params: P.notebook,
    payload: S.Custom,
  });
  const status = HttpApiEndpoint.get("status", "/status");
  const {
    Api,
    events: { NotebookStreamEvent },
  } = makeHostContract([
    analysis,
    defineFeature({
      catalog: { endpoints: [status] },
      notebook: { endpoints: [emit] },
    }),
  ]);

  type Client = HttpApiClient.ForApi<typeof Api>;
  type Request = Parameters<Client["Notebook"]["emit"]>[0];
  expectTypeOf<Request["payload"]>().toEqualTypeOf<typeof S.Custom.Type>();
  type AnalysisEvent = Extract<
    typeof NotebookStreamEvent.Type,
    { event: "analysis" }
  >;
  expectTypeOf<
    AnalysisEvent["data"]["analysis"]["notebook_id"]
  >().toEqualTypeOf<typeof S.NotebookId.Type>();

  const path = "/notebooks/{notebook_id}/emit";
  expect(Api.groups.Host.endpoints).toHaveProperty("status");
  expect(Api.groups.Notebook.endpoints).not.toHaveProperty("status");
  expect(
    OpenApi.fromApi(Api, { referencePolicy }).paths[path].post?.security,
  ).toEqual([{ hostToken: [] }]);
  expect(stable.paths).not.toHaveProperty(path);
});
