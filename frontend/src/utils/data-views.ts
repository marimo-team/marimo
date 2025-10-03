/* Copyright 2024 Marimo. All rights reserved. */
import { set } from "lodash-es";
import { invariant } from "./invariant";
import { Logger } from "./Logger";

/**
 * Update the object with DataView buffers at the specified paths.
 */
export function updateBufferPaths<T extends Record<string, unknown>>(
  inputObject: T,
  bufferPaths: readonly (readonly (string | number)[])[],
  buffers: readonly DataView[],
): T {
  // If no buffer paths, return the original object
  if (!bufferPaths || bufferPaths.length === 0) {
    return inputObject;
  }

  // If has buffers, assert they are the same size
  if (buffers) {
    invariant(
      buffers.length === bufferPaths.length,
      "Buffers and buffer paths not the same length",
    );
  }

  let object = structuredClone(inputObject);

  for (const [i, bufferPath] of bufferPaths.entries()) {
    // If buffers exists, we use that value
    // Otherwise we grab it from inside the inputObject
    const dataView = buffers[i];
    if (!dataView) {
      Logger.warn("Could not find buffer at path", bufferPath);
      continue;
    }
    object = set(object, bufferPath, dataView);
  }

  return object;
}
