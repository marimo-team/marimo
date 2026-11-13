/* Copyright 2026 Marimo. All rights reserved. */

import { Schema, SchemaGetter } from "effect";
import { HttpApiSchema } from "effect/http-api";

export function sseEvents<S extends Schema.Constraint>(events: S) {
  return Schema.Struct({
    event: Schema.String,
    id: Schema.optionalKey(Schema.String),
    data: Schema.fromJsonString(Schema.Json),
  }).pipe(Schema.decodeTo(events));
}

export function response<A, I, const Status extends number>(
  body: Schema.Codec<A, I>,
  status: Status,
) {
  return body.pipe(
    Schema.decodeTo(
      Schema.Struct({
        status: Schema.Literal(status),
        body: Schema.toType(body),
      }),
      {
        decode: SchemaGetter.transform((body) => ({ status, body })),
        encode: SchemaGetter.transform(({ body }) => body),
      },
    ),
    HttpApiSchema.status(status),
  );
}
