/* Copyright 2024 Marimo. All rights reserved. */
import { Facet } from "@codemirror/state";

/**
 * A facet that combines a single value.
 *
 * This is useful for creating a facet that can be used to store a single value.
 *
 * @example
 * ```ts
 * const myFacet = singleFacet<string>();
 * const myValue = myFacet.of("hello");
 * ```
 */
export function singleFacet<T>() {
  return Facet.define<T, T>({
    combine: (values) => values[0],
  });
}
