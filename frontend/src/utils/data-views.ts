/* Copyright 2024 Marimo. All rights reserved. */
import { get, set } from "lodash-es";
import { invariant } from "./invariant";
import { Logger } from "./Logger";
import { byteStringToBinary, typedAtob, type Base64String } from "./json/base64";

/**
 * Convert a DataView to a base64 string.
 */
export function dataViewToBase64(dataView: DataView): string {
  const bytes = new Uint8Array(
    dataView.buffer,
    dataView.byteOffset,
    dataView.byteLength,
  );
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

/**
 * Recursively find all DataViews in an object and return their paths.
 *
 * This mirrors ipywidgets' _separate_buffers logic.
 */
function findDataViewPaths(
  obj: unknown,
  currentPath: (string | number)[] = [],
): (string | number)[][] {
  const paths: (string | number)[][] = [];

  if (obj instanceof DataView) {
    paths.push(currentPath);
  } else if (Array.isArray(obj)) {
    for (let i = 0; i < obj.length; i++) {
      paths.push(...findDataViewPaths(obj[i], [...currentPath, i]));
    }
  } else if (obj !== null && typeof obj === "object") {
    for (const [key, value] of Object.entries(obj)) {
      paths.push(...findDataViewPaths(value, [...currentPath, key]));
    }
  }

  return paths;
}

/**
 * Serialize DataView buffers to base64 strings.
 *
 * Finds all DataViews in the object.
 */
export function serializeBuffersToBase64<T extends Record<string, unknown>>(
  inputObject: T,
): { state: T; buffers: string[]; bufferPaths: (string | number)[][] } {
  // Dynamically find all DataView paths instead of using fixed bufferPaths
  const dataViewPaths = findDataViewPaths(inputObject);

  if (dataViewPaths.length === 0) {
    return { state: inputObject, buffers: [], bufferPaths: [] };
  }

  const state = structuredClone(inputObject);
  const buffers: string[] = [];
  const bufferPaths: (string | number)[][] = [];

  for (const bufferPath of dataViewPaths) {
    const dataView = get(inputObject, bufferPath);
    if (dataView instanceof DataView) {
      const base64 = dataViewToBase64(dataView);
      buffers.push(base64);
      bufferPaths.push(bufferPath);
      set(state, bufferPath, base64);
    }
  }

  return { state, buffers, bufferPaths };
}

/**
 * Wire format for anywidget state with binary data.
 */
export interface WireFormat<T = Record<string, unknown>> {
  state: T;
  bufferPaths: (string | number)[][];
  buffers: Base64String[];
}

/**
 * Check if an object is in wire format.
 */
export function isWireFormat(obj: unknown): obj is WireFormat {
  return (
    obj !== null &&
    typeof obj === "object" &&
    "state" in obj &&
    "bufferPaths" in obj &&
    "buffers" in obj
  );
}

/**
 * Decode wire format { state, bufferPaths, buffers } to plain state with DataViews.
 *
 * For ndarray-like structures {view: null, dtype, shape}, we insert the DataView
 * at the 'view' key, preserving the structure for round-tripping.
 */
export function decodeFromWire<T extends Record<string, unknown>>(
  wire: WireFormat<T>,
): T {
  const { state, bufferPaths, buffers } = wire;

  if (!bufferPaths || bufferPaths.length === 0) {
    return state;
  }

  const out = structuredClone(state);
  for (let i = 0; i < bufferPaths.length; i++) {
    const bufferPath = bufferPaths[i];
    const base64String = buffers[i];
    if (base64String) {
      const bytes = byteStringToBinary(typedAtob(base64String));
      set(out, bufferPath, new DataView(bytes.buffer));
    }
  }
  return out;
}

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
