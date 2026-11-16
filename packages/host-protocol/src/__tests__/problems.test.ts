/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import { Effect, Schema } from "effect";
import { describe, expect, it } from "vitest";
import * as Problems from "../Problems.ts";
import * as Host from "../Host.ts";
import * as Notebook from "../Notebook.ts";

const fixtures = new URL(
  "../../../../protocols/host/fixtures/problems/",
  import.meta.url,
);
function fixture(name: string): unknown {
  return JSON.parse(readFileSync(new URL(`${name}.json`, fixtures), "utf8"));
}

it.each([
  ["not-found", Problems.NotFoundProblem],
  ["conflict", Problems.ConflictProblem],
  ["precondition-failed", Problems.PreconditionFailedProblem],
  ["decision-required", Problems.DecisionRequiredProblem],
  ["no-runtime", Problems.NoRuntimeProblem],
  ["unsupported-operation", Problems.UnsupportedOperationProblem],
] as const)(
  "decodes %s into its error class without changing the wire payload",
  (name, ErrorClass) => {
    const input = fixture(name);
    const error = Schema.decodeUnknownSync(Problems.Problem)(input);
    expect(error).toBeInstanceOf(ErrorClass);
    expect(Schema.encodeSync(Problems.Problem)(error)).toEqual(input);
  },
);

it("constructs errors with required actionable details", () => {
  const decisions = [
    {
      id: "environment",
      prompt: "Where?",
      options: [{ id: "local", label: "Local" }],
    },
  ];
  const error = new Problems.DecisionRequiredProblem({ decisions });
  expect(Schema.encodeSync(Problems.DecisionRequiredProblem)(error)).toEqual({
    type: "urn:marimo:problem:decision-required",
    status: 409,
    title: "Decision required",
    decisions,
  });
  const task = Effect.gen(function* () {
    return yield* error;
  });
  expect(
    Effect.runSync(
      task.pipe(
        Effect.catchTag("DecisionRequiredProblem", (error) =>
          Effect.succeed(error.decisions),
        ),
      ),
    ),
  ).toEqual(decisions);
});

it.each([
  { type: "decision-required", status: 409 },
  { type: "decision-required", status: 409, decisions: null },
  { type: "decision-required", status: 409, decisions: [{}] },
  { type: "precondition-failed", status: 412 },
  { type: "precondition-failed", status: 412, index: 0, cell: null },
])("rejects a malformed defined problem: %j", (input) => {
  expect(() =>
    Schema.decodeUnknownSync(Problems.Problem)({
      ...input,
      type: `urn:marimo:problem:${input.type}`,
      title: "Problem",
    }),
  ).toThrow(Schema.SchemaError);
});

it("preserves an unknown problem's entire JSON body", () => {
  const input = {
    type: "tag:example.com,2026:quota",
    title: "Quota exceeded",
    status: 429,
    detail: "Retry later",
    retry_after: 60,
    metadata: { values: [1, null, true] },
  };
  const problem = Schema.decodeUnknownSync(Problems.UnknownProblem)(input);
  expect(problem).toEqual(input);
  expect(Schema.encodeSync(Problems.UnknownProblem)(problem)).toEqual(input);
  expect(() => Schema.decodeUnknownSync(Problems.Problem)(input)).toThrow(
    Schema.SchemaError,
  );
});

it.each([
  { type: "future/problem", title: "Future", status: 200 },
  { type: "future/problem", title: "Future", status: 429.5 },
  { type: "future/problem", title: "Future", status: 600 },
  { type: "future/problem", title: "Future" },
  { type: "future/problem", status: 429 },
  { title: "Future", status: 429 },
])("rejects a malformed problem envelope: %j", (input) => {
  expect(() =>
    Schema.decodeUnknownSync(Problems.UnknownProblem)(input),
  ).toThrow(Schema.SchemaError);
});

it.each([
  [Notebook.Save, "decision-required", true],
  [Notebook.Start, "decision-required", true],
  [Notebook.Edit, "decision-required", false],
  [Host.Create, "no-runtime", false],
  [Notebook.Start, "no-runtime", false],
  [Notebook.Stop, "no-runtime", true],
  [Notebook.Restart, "no-runtime", true],
  [Notebook.Run, "no-runtime", true],
  [Notebook.Interrupt, "no-runtime", true],
  [Notebook.Cancel, "no-runtime", false],
  [Notebook.Edit, "precondition-failed", true],
  [Notebook.Save, "precondition-failed", true],
  [Notebook.Run, "precondition-failed", true],
  [Notebook.Delete, "precondition-failed", false],
] as const)(
  "restricts %s to its declared errors (%s)",
  (rpc, name, accepted) => {
    const schema = Schema.toEncoded(Schema.Union([...rpc.error]));
    expect(Schema.is(schema)(fixture(name))).toBe(accepted);
  },
);

describe("tagged problem errors", () => {
  it.each([
    Problems.InvalidRequestProblem,
    Problems.UnauthorizedProblem,
    Problems.ForbiddenProblem,
    Problems.NotFoundProblem,
    Problems.MethodNotAllowedProblem,
    Problems.ConflictProblem,
    Problems.NoRuntimeProblem,
    Problems.InternalProblem,
    Problems.UnsupportedOperationProblem,
  ])("round-trips %s without serializing the Effect tag", (ErrorClass) => {
    const error = new ErrorClass({ detail: "Details" });
    const schema: Schema.Codec<unknown, unknown> = ErrorClass;
    const wire = Schema.encodeSync(schema)(error);
    expect(wire).toEqual({
      type: error.type,
      status: error.status,
      title: error.title,
      detail: "Details",
    });
    const decoded = Schema.decodeUnknownSync(schema)(wire);
    expect(decoded).toBeInstanceOf(ErrorClass);
    expect(decoded).toMatchObject({
      _tag: error._tag,
      type: error.type,
      status: error.status,
    });
  });

  it("supports yielding errors and recovering with catchTag", () => {
    const task = Effect.gen(function* () {
      return yield* new Problems.NotFoundProblem({
        detail: "Notebook not found",
      });
    });
    const result = task.pipe(
      Effect.catchTag("NotFoundProblem", (error) =>
        Effect.succeed(error.detail),
      ),
    );
    expect(Effect.runSync(result)).toBe("Notebook not found");
  });

  it("requires the wire type and keeps the declared status and title", () => {
    const decode = Schema.decodeUnknownSync(Problems.NotFoundProblem);
    expect(() => decode({ title: "Missing", status: 404 })).toThrow(
      Schema.SchemaError,
    );
    expect(
      decode({
        title: "Missing",
        type: "urn:marimo:problem:not-found",
        status: 409,
      }),
    ).toMatchObject({ status: 404, title: "Not found" });
  });
});
