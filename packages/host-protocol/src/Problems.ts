/* Copyright 2026 Marimo. All rights reserved. */

/** The problems a host answers with, as RFC 9457 problem details. */

import { Schema } from "effect";
import { HttpApiError } from "effect/http-api";
import { Integer } from "./internal/schema.ts";
import { Cell, Document } from "./model/Document.ts";

const type = <const Kind extends string>(kind: Kind) =>
  `urn:marimo:problem:${kind}` as const;

export const DecisionOption = Schema.Struct({
  id: Schema.String.annotateKey({ description: "Identifies this answer." }),
  label: Schema.String.annotateKey({
    description: "Text to show a person.",
    examples: ["Sandbox from the notebook's dependencies"],
  }),
}).annotate({
  description: "One possible answer to a decision.",
  identifier: "DecisionOption",
});

export const Decision = Schema.Struct({
  id: Schema.String.annotateKey({
    description: "Identifies the question when the client answers it.",
  }),
  prompt: Schema.String.annotateKey({
    description: "The question, worded for a person.",
    examples: ["Where should forecasts.py run?"],
  }),
  options: Schema.Array(DecisionOption).annotateKey({
    description: "The possible answers.",
  }),
}).annotate({
  description:
    "A question the host needs answered before it can carry out a\nrequest. The client answers by repeating the request with\n`decisions` in the body, mapping this `id` to the `id` of an\noption.\n",
  identifier: "Decision",
});

export class InvalidRequestProblem extends HttpApiError.Problem<InvalidRequestProblem>()(
  "InvalidRequestProblem",
  { type: type("invalid-request"), status: 400, title: "Invalid request" },
  {},
  { description: "The request is malformed or could not apply to any state." },
) {}

export class UnauthorizedProblem extends HttpApiError.Problem<UnauthorizedProblem>()(
  "UnauthorizedProblem",
  { type: type("unauthorized"), status: 401, title: "Unauthorized" },
  {},
  { description: "The token is missing or wrong." },
) {}

export class ForbiddenProblem extends HttpApiError.Problem<ForbiddenProblem>()(
  "ForbiddenProblem",
  { type: type("forbidden"), status: 403, title: "Forbidden" },
  {},
  {
    description:
      "The request did not come from this machine, or the object's `operations` do not permit this client to call the operation.",
  },
) {}

export class NotFoundProblem extends HttpApiError.Problem<NotFoundProblem>()(
  "NotFoundProblem",
  { type: type("not-found"), status: 404, title: "Not found" },
  {},
  { description: "The requested object or route was not found." },
) {}

export class MethodNotAllowedProblem extends HttpApiError.Problem<MethodNotAllowedProblem>()(
  "MethodNotAllowedProblem",
  {
    type: type("method-not-allowed"),
    status: 405,
    title: "Method not allowed",
  },
  {},
  {
    description:
      "The route exists but not for this method. The `Allow` header lists the methods it accepts.",
  },
) {}

export class ConflictProblem extends HttpApiError.Problem<ConflictProblem>()(
  "ConflictProblem",
  { type: type("conflict"), status: 409, title: "Conflict" },
  {},
  { description: "The current state does not allow the request." },
) {}

export class NoRuntimeProblem extends HttpApiError.Problem<NoRuntimeProblem>()(
  "NoRuntimeProblem",
  { type: type("no-runtime"), status: 409, title: "No runtime" },
  {},
  { description: "The request needs a runtime and the notebook has none." },
) {}

export class DecisionRequiredProblem extends HttpApiError.Problem<DecisionRequiredProblem>()(
  "DecisionRequiredProblem",
  {
    type: type("decision-required"),
    status: 409,
    title: "Decision required",
  },
  {
    decisions: Schema.Array(Decision).annotateKey({
      description:
        "The choices the client has to make before the host can carry out the request.",
    }),
  },
  {
    description:
      "The host needs a choice from the client before it can carry out the request.",
  },
) {}

export class PreconditionFailedProblem extends HttpApiError.Problem<PreconditionFailedProblem>()(
  "PreconditionFailedProblem",
  {
    type: type("precondition-failed"),
    status: 412,
    title: "Precondition failed",
  },
  {
    index: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
      description:
        "The position of the first stale entry in the request, counted in an edit's `changes` or a run's `cells`. `0` for a save with a stale `If-Match`.",
    }),
    cell: Schema.NullOr(Cell).annotateKey({
      description:
        "The cell that entry named, as it now is. Null when the document does not have it, or when the entry named the order or the whole document.",
    }),
    document: Document.annotateKey({
      description: "The document as it now is.",
    }),
  },
  {
    description:
      "The request named a state the document no longer has. The problem carries the cell and the document as they now are.",
  },
) {}

export class InternalProblem extends HttpApiError.Problem<InternalProblem>()(
  "InternalProblem",
  { type: type("internal"), status: 500, title: "Internal error" },
  {},
  { description: "The host failed." },
) {}

export class UnsupportedOperationProblem extends HttpApiError.Problem<UnsupportedOperationProblem>()(
  "UnsupportedOperationProblem",
  {
    type: type("unsupported-operation"),
    status: 501,
    title: "Unsupported operation",
  },
  {},
  {
    description:
      "The host does not offer this operation. Its `operations` list says which it does.",
  },
) {}

export const Common = Schema.Union([
  InvalidRequestProblem,
  ForbiddenProblem,
  NotFoundProblem,
  InternalProblem,
]);

export const Mutation = Schema.Union([
  ...Common.members,
  ConflictProblem,
  UnsupportedOperationProblem,
]);

export const Http = Schema.Union([
  UnauthorizedProblem,
  MethodNotAllowedProblem,
]);

/** Every problem this version defines. `type` tells them apart. */
export const Problem = Schema.Union([
  InvalidRequestProblem,
  UnauthorizedProblem,
  ForbiddenProblem,
  NotFoundProblem,
  MethodNotAllowedProblem,
  ConflictProblem,
  NoRuntimeProblem,
  DecisionRequiredProblem,
  PreconditionFailedProblem,
  InternalProblem,
  UnsupportedOperationProblem,
]).annotate({
  description:
    "An error. Every error response is a problem, following RFC 9457, and is served as `application/problem+json`. `type` says which. A client ignores members it does not recognize. Hosts redact tokens from errors.",
  identifier: "Problem",
});

/** The members every problem has, for a type this version does not define. */
export const UnknownProblem = Schema.StructWithRest(
  Schema.Struct({
    type: Schema.String.annotateKey({
      description: "What kind of problem this is, as a URI.",
    }),
    title: Schema.String.annotateKey({
      description: "A short, human-readable name for the kind of problem.",
    }),
    status: Integer.check(
      Schema.isGreaterThanOrEqualTo(400),
      Schema.isLessThanOrEqualTo(599),
    ).annotateKey({ description: "The HTTP status code of the response." }),
    detail: Schema.optionalKey(
      Schema.String.annotateKey({
        description:
          "A human-readable explanation of what went wrong this time.",
      }),
    ),
  }),
  [Schema.Record(Schema.String, Schema.Json)],
).annotate({
  description:
    "A problem of a type this version does not define. A host on a later version can send one, and a client falls back to its `status`.",
  identifier: "UnknownProblem",
});
