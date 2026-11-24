/* Copyright 2026 Marimo. All rights reserved. */

import { type Array as Arr, Schema, SchemaGetter } from "effect";
import {
  type HttpApiEndpoint,
  HttpApiGroup,
  HttpApiSchema,
} from "effect/http-api";

export function makeGroup<
  const Id extends string,
  const Endpoints extends Arr.NonEmptyReadonlyArray<HttpApiEndpoint.Constraint>,
>(id: Id, ...endpoints: Endpoints) {
  const names = new Set<string>();
  for (const endpoint of endpoints) {
    if (names.has(endpoint.identifier)) {
      throw new Error(`Duplicate endpoint: ${id}.${endpoint.identifier}`);
    }
    names.add(endpoint.identifier);
  }
  return HttpApiGroup.make(id).add(...endpoints);
}

export function sseEvents<S extends Schema.Constraint>(events: S) {
  // The frame is a transport detail, so it does not take the union's name.
  return Schema.Struct({
    event: Schema.String,
    id: Schema.optionalKey(Schema.String),
    data: Schema.fromJsonString(Schema.Json),
  }).pipe(Schema.decodeTo(events), Schema.annotate({ identifier: undefined }));
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
