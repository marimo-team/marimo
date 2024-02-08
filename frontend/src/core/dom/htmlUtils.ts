/* Copyright 2024 Marimo. All rights reserved. */
import { assertExists } from "@/utils/assertExists";
import { UI_ELEMENT_REGISTRY } from "./uiregistry";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { Objects } from "@/utils/objects";
import { UIElementId } from "../cells/ids";

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
export function parseInitialValue<T>(element: HTMLElement): T {
  // If parent is a <marimo-ui-element/> and has object-id, use that as the initialize the value
  const objectId = element.parentElement
    ? UIElementId.parse(element.parentElement)
    : undefined;
  if (objectId && UI_ELEMENT_REGISTRY.has(objectId)) {
    return UI_ELEMENT_REGISTRY.lookupValue(objectId) as T;
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
  const filenameTag = document.querySelector("marimo-filename");
  assertExists(filenameTag, "marimo-filename tag not found");
  const name = filenameTag.innerHTML;
  return name.length === 0 ? null : name;
}
