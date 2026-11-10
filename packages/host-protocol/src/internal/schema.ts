/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";

// The protocol's integers are not restricted to JavaScript's safe-integer range.
export const Integer = Schema.Number.check(
  Schema.isFinite(),
  Schema.makeFilter(Number.isInteger, {
    expected: "an integer",
    toJsonSchema: () => ({ type: "integer" }),
  }),
);

export function closedStruct<const Fields extends Schema.Struct.Fields>(
  fields: Fields,
) {
  const struct = Schema.Struct(fields);
  // Retain extra keys until the closed-object check has seen them.
  const closed = Schema.StructWithRest(struct, [
    Schema.Record(Schema.String, Schema.Unknown),
  ]).check(
    Schema.makeFilter(
      (value) => Object.keys(value).every((key) => Object.hasOwn(fields, key)),
      {
        expected: "an object without extra properties",
        toJsonSchema: () => ({ additionalProperties: false }),
      },
    ),
  );
  return struct.rebuild(closed.ast);
}
