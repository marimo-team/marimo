/* Copyright 2024 Marimo. All rights reserved. */
import { get, set } from "lodash-es";
import { Logger } from "./Logger";
import { type ByteString, typedAtob, type Base64String } from "./json/base64";
import { invariant } from "./invariant";

/**
 * Update the object with DataView buffers at the specified paths.
 */
export function updateBufferPaths<T extends Record<string, unknown>>(
  inputObject: T,
  bufferPaths: Array<Array<string | number>> | null | undefined,
  buffers?: Base64String[] | null | undefined,
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
    const bytes: ByteString = buffers
      ? typedAtob(buffers[i])
      : get(object, bufferPath);
    if (!bytes) {
      Logger.warn("Could not find buffer at path", bufferPath);
      continue;
    }
    const buffer = byteStringToDataView(bytes);
    object = set(object, bufferPath, buffer);
  }

  return object;
}

export const byteStringToDataView = (bytes: ByteString) => {
  const buffer = new ArrayBuffer(bytes.length);
  const view = new DataView(buffer);
  for (let i = 0; i < bytes.length; i++) {
    view.setUint8(i, bytes.charCodeAt(i));
  }
  return view;
};
