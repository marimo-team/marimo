/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { Timestamp } from "../model/Ids.ts";

export const Cursor = Schema.String.check(
  Schema.isMinCodePoints(1),
).annotateKey({
  description: "The resume cursor. Omitted on snapshot and reset events.",
});

export function message<const Fields extends Schema.Struct.Fields>(
  fields: Fields,
) {
  return Schema.Struct({
    request_id: Schema.optionalKey(
      Schema.String.annotateKey({
        description:
          "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      }),
    ),
    time: Schema.optionalKey(
      Timestamp.annotateKey({
        description:
          "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      }),
    ),
    ...fields,
  });
}

export function event<
  const Name extends string,
  Data extends Schema.Constraint,
  Id extends Schema.Constraint,
>(name: Name, data: Data, options: { readonly id: Id }) {
  return Schema.Struct({ event: Schema.Literal(name), id: options.id, data });
}
