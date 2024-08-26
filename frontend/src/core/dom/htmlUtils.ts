/* Copyright 2024 Marimo. All rights reserved. */
import { assertExists } from "@/utils/assertExists";
import type { UIElementRegistry } from "./uiregistry";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { Objects } from "@/utils/objects";
import { UIElementId } from "../cells/ids";
import { isWasm } from "../wasm/utils";
import { PyodideRouter } from "../wasm/router";

/**
 * Parse an attribute value as JSON.
 */
export function parseAttrValue<T>(value: string | undefined): T {
  return jsonParseWithSpecialChar(value ?? "");
}

export function parseDataset(element: HTMLElement): Record<string, unknown> {
  return Objects.mapValues(element.dataset, (value) =>
    typeof value === "string" ? parseAttrValue(value) : value,
  );
}

/**
 * Parse the initial value.
 * It will first check if the parent element is a <marimo-ui-element/> with an object-id that
 * exist in the UI registry.
 * And otherwise fallback to the data-initial-value attribute.
 */
export function parseInitialValue<T>(
  element: HTMLElement,
  registry: UIElementRegistry,
): T {
  // If parent is a <marimo-ui-element/> and has object-id, use that as the initialize the value
  const objectId = element.parentElement
    ? UIElementId.parse(element.parentElement)
    : undefined;
  if (objectId && registry.has(objectId)) {
    return registry.lookupValue(objectId) as T;
  }

  // Otherwise use the data-initial-value attribute
  return parseAttrValue(element.dataset.initialValue);
}

/**
 * Serialize the initial value.
 */
export function serializeInitialValue(value: unknown) {
  return JSON.stringify(value);
}

export function getFilenameFromDOM() {
  // If we are running in WASM, we can get the filename from the URL
  if (isWasm()) {
    const filename = PyodideRouter.getFilename();
    if (filename) {
      return filename;
    }
  }

  const filenameTag = document.querySelector("marimo-filename");
  if (!filenameTag) {
    return null;
  }

  const name = filenameTag.innerHTML;
  return name.length === 0 ? null : name;
}
