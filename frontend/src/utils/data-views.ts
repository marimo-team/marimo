/* Copyright 2024 Marimo. All rights reserved. */
import { get, set } from "lodash-es";
import { Logger } from "./Logger";

/**
 * Update the object with DataView buffers at the specified paths.
 */
export function updateBufferPaths<T extends object>(
  inputObject: T,
  bufferPaths: Array<Array<string | number>> | null | undefined,
): T {
  // If no buffer paths, return the original object
  if (!bufferPaths || bufferPaths.length === 0) {
    return inputObject;
  }

  let object = structuredClone(inputObject);

  for (const bufferPath of bufferPaths) {
    const bytes = get(object, bufferPath);
    if (!bytes) {
      Logger.warn("Could not find buffer at path", bufferPath);
      continue;
    }
    const buffer = base64ToDataView(bytes);
    object = set(object, bufferPath, buffer);
  }

  return object;
}

export const base64ToDataView = (bytes: string) => {
  const buffer = new ArrayBuffer(bytes.length);
  const view = new DataView(buffer);
  for (let i = 0; i < bytes.length; i++) {
    view.setUint8(i, bytes.charCodeAt(i));
  }
  return view;
};
