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
