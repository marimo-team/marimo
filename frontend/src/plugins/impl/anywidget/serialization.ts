/* Copyright 2026 Marimo. All rights reserved. */
import { get, set } from "lodash-es";
import { invariant } from "../../../utils/invariant";
import {
  type Base64String,
  base64ToDataView,
  dataViewToBase64,
} from "../../../utils/json/base64";
import { Logger } from "../../../utils/Logger";
import type { WireFormat } from "./types";

type Path = (string | number)[];

/**
 * Recursively find all DataViews in an object and return their paths.
 *
 * This mirrors ipywidgets' _separate_buffers logic.
 */
function findDataViewPaths(obj: unknown, currentPath: Path = []): Path[] {
  const paths: Path[] = [];

  if (obj instanceof DataView) {
    paths.push(currentPath);
  } else if (Array.isArray(obj)) {
    for (const [i, element] of obj.entries()) {
      paths.push(...findDataViewPaths(element, [...currentPath, i]));
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
  const bufferPaths: Path[] = [];

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
  bufferPaths?: Path[];
  buffers?: readonly (DataView | Base64String)[];
}): T {
  const { state, bufferPaths, buffers } = input;

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

  // We should avoid using structuredClone if possible since
  // it can be very slow. If mutability is a concern, we should use a different approach.
  const out = state;

  for (const [i, bufferPath] of bufferPaths.entries()) {
    const buffer = buffers?.[i];

    if (buffer == null) {
      Logger.warn("[anywidget] Could not find buffer at path", bufferPath);
      continue;
    }

    // Handle both base64 strings (from wire format) and DataViews (direct usage)
    if (typeof buffer === "string") {
      set(out, bufferPath, base64ToDataView(buffer));
    } else {
      set(out, bufferPath, buffer);
    }
  }

  return out;
}
