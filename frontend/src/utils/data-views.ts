/* Copyright 2024 Marimo. All rights reserved. */
import { get, set } from "lodash-es";
import { invariant } from "./invariant";
import {
  type Base64String,
  binaryToByteString,
  byteStringToBinary,
  typedAtob,
  typedBtoa,
} from "./json/base64";
import { Logger } from "./Logger";

/**
 * Convert a DataView to a base64 string.
 */
export function dataViewToBase64(dataView: DataView): Base64String {
  const bytes = new Uint8Array(
    dataView.buffer,
    dataView.byteOffset,
    dataView.byteLength,
  );
  const byteString = binaryToByteString(bytes);
  return typedBtoa(byteString);
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
): WireFormat<T> {
  // Dynamically find all DataView paths instead of using fixed bufferPaths
  const dataViewPaths = findDataViewPaths(inputObject);

  if (dataViewPaths.length === 0) {
    return { state: inputObject, buffers: [], bufferPaths: [] };
  }

  const state = structuredClone(inputObject);
  const buffers: Base64String[] = [];
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
 * Buffers can be either base64 strings (from network) or DataViews (in-memory).
 */
export interface WireFormat<T = Record<string, unknown>> {
  state: T;
  bufferPaths: (string | number)[][];
  buffers: Base64String[];
}

/**
 * Check if an object is in wire format.
 */
export function isWireFormat<T = Record<string, unknown>>(
  obj: unknown,
): obj is WireFormat<T> {
  return (
    obj !== null &&
    typeof obj === "object" &&
    "state" in obj &&
    "bufferPaths" in obj &&
    "buffers" in obj
  );
}

/**
 * Decode wire format or insert DataViews at specified paths.
 *
 * Accepts either:
 * 1. Wire format: { state, bufferPaths, buffers } where buffers are base64 strings
 * 2. Direct format: { state, bufferPaths, buffers } where buffers are DataViews
 *
 * For ndarray-like structures {view: null, dtype, shape}, we insert the DataView
 * at the 'view' key, preserving the structure for round-tripping.
 */
export function decodeFromWire<T extends Record<string, unknown>>(input: {
  state: T;
  bufferPaths?: (string | number)[][];
  buffers?: readonly (DataView | Base64String)[];
}): T {
  const { state, bufferPaths, buffers } = structuredClone(input);

  // If no buffer paths, return the original state
  if (!bufferPaths || bufferPaths.length === 0) {
    return state;
  }

  // If has buffers, assert they are the same size
  if (buffers) {
    invariant(
      buffers.length === bufferPaths.length,
      "Buffers and buffer paths not the same length",
    );
  }

  const out = structuredClone(state);

  for (const [i, bufferPath] of bufferPaths.entries()) {
    const buffer = buffers?.[i];

    if (buffer == null) {
      Logger.warn("[anywidget] Could not find buffer at path", bufferPath);
      continue;
    }

    // Handle both base64 strings (from wire format) and DataViews (direct usage)
    if (typeof buffer === "string") {
      const bytes = byteStringToBinary(typedAtob(buffer));
      set(out, bufferPath, new DataView(bytes.buffer));
    } else {
      set(out, bufferPath, buffer);
    }
  }

  return out;
}
