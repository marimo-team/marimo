/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { EditConflict } from "./edits.ts";

const fields = <
  const Kind extends string,
  const Status extends number,
  const Title extends string,
>(
  identifier: string,
  kind: Kind,
  status: Status,
  title: Title,
) =>
  Schema.Struct({
    type: Schema.tag(`tag:marimo.io,2026:host/${kind}`),
    title: Schema.tag(title),
    status: Schema.tag(status),
    detail: Schema.optionalKey(Schema.String),
  }).annotate({ identifier });

const annotations = (status: number) => ({
  httpApiStatus: status,
  "~httpApiEncoding": {
    _tag: "Json" as const,
    contentType: "application/problem+json",
  },
});

export class InvalidRequest extends Schema.Error<InvalidRequest>(
  "InvalidRequest",
)(
  fields("InvalidRequest", "invalid-request", 400, "Invalid request"),
  annotations(400),
) {
  get _tag() {
    return "InvalidRequest" as const;
  }
}

export class Unauthorized extends Schema.Error<Unauthorized>("Unauthorized")(
  fields("Unauthorized", "unauthorized", 401, "Unauthorized"),
  annotations(401),
) {
  get _tag() {
    return "Unauthorized" as const;
  }
}

export class NotFound extends Schema.Error<NotFound>("NotFound")(
  fields("NotFound", "not-found", 404, "Not found"),
  annotations(404),
) {
  get _tag() {
    return "NotFound" as const;
  }
}

export class Conflict extends Schema.Error<Conflict>("Conflict")(
  Schema.Struct({
    ...fields("Conflict", "conflict", 409, "Conflict").fields,
    edit: Schema.optionalKey(EditConflict),
  }).annotate({ identifier: "Conflict" }),
  annotations(409),
) {
  get _tag() {
    return "Conflict" as const;
  }
}

export class UnsupportedOperation extends Schema.Error<UnsupportedOperation>(
  "UnsupportedOperation",
)(
  fields(
    "UnsupportedOperation",
    "unsupported-operation",
    501,
    "Unsupported operation",
  ),
  annotations(501),
) {
  get _tag() {
    return "UnsupportedOperation" as const;
  }
}

export class Forbidden extends Schema.Error<Forbidden>("Forbidden")(
  fields("Forbidden", "forbidden", 403, "Forbidden"),
  annotations(403),
) {
  get _tag() {
    return "Forbidden" as const;
  }
}

export class MethodNotAllowed extends Schema.Error<MethodNotAllowed>(
  "MethodNotAllowed",
)(
  fields("MethodNotAllowed", "method-not-allowed", 405, "Method not allowed"),
  annotations(405),
) {
  get _tag() {
    return "MethodNotAllowed" as const;
  }
}

export class NotAcceptable extends Schema.Error<NotAcceptable>("NotAcceptable")(
  fields("NotAcceptable", "not-acceptable", 406, "Not acceptable"),
  annotations(406),
) {
  get _tag() {
    return "NotAcceptable" as const;
  }
}

export class NoRuntime extends Schema.Error<NoRuntime>("NoRuntime")(
  fields("NoRuntime", "no-runtime", 409, "No runtime"),
  annotations(409),
) {
  get _tag() {
    return "NoRuntime" as const;
  }
}

export class Internal extends Schema.Error<Internal>("Internal")(
  fields("Internal", "internal", 500, "Internal error"),
  annotations(500),
) {
  get _tag() {
    return "Internal" as const;
  }
}

export const DecisionOption = Schema.Struct({
  id: Schema.String,
  label: Schema.String,
}).annotate({ identifier: "DecisionOption" });
export type DecisionOption = typeof DecisionOption.Type;
export const Decision = Schema.Struct({
  id: Schema.String,
  prompt: Schema.String,
  options: Schema.Array(DecisionOption),
}).annotate({ identifier: "Decision" });
export type Decision = typeof Decision.Type;
export class DecisionRequired extends Schema.Error<DecisionRequired>(
  "DecisionRequired",
)(
  Schema.Struct({
    ...fields("DecisionRequired", "decision-required", 409, "Decision required")
      .fields,
    decisions: Schema.Array(Decision),
  }).annotate({ identifier: "DecisionRequired" }),
  annotations(409),
) {
  get _tag() {
    return "DecisionRequired" as const;
  }
}
export const Problem = Schema.Struct({
  type: Schema.String,
  title: Schema.String,
  status: Schema.Int.check(
    Schema.isGreaterThanOrEqualTo(400),
    Schema.isLessThanOrEqualTo(599),
  ),
  detail: Schema.optionalKey(Schema.String),
  decisions: Schema.optionalKey(Schema.Array(Decision)),
  edit: Schema.optionalKey(EditConflict),
}).annotate({ identifier: "Problem" });
export type Problem = typeof Problem.Type;
export const HostError = Schema.Union([
  InvalidRequest,
  Unauthorized,
  Forbidden,
  NotFound,
  MethodNotAllowed,
  NotAcceptable,
  Conflict,
  NoRuntime,
  DecisionRequired,
  Internal,
  UnsupportedOperation,
]);
export type HostError = typeof HostError.Type;
