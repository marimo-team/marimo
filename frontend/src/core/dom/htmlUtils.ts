/* Copyright 2023 Marimo. All rights reserved. */
import { assertExists } from "@/utils/assertExists";
import { UI_ELEMENT_REGISTRY } from "./uiregistry";

// Random unicode character that is unlikely to be used in the JSON string
const CHAR = "◐";

/**
 * Parse an attribute value as JSON.
 */
export function parseAttrValue<T>(value: string | undefined): T {
  try {
    // This will properly handle NaN, Infinity, and -Infinity
    // The python json.dumps encoding will serialize to NaN, Infinity, -Infinity which is not valid JSON,
    // but we don't want to change the python encoding because NaN, Infinity, -Infinity are valuable to know.
    value = value ?? "";
    value = value.replaceAll(
      // This was iterated on with GPT. The confidence lies in the unit tests.
      /(?<=\s|^|\[|,|:)(NaN|-Infinity|Infinity)(?=(?:[^"'\\]*(\\.|'([^'\\]*\\.)*[^'\\]*'|"([^"\\]*\\.)*[^"\\]*"))*[^"']*$)/g,
      `"${CHAR}$1${CHAR}"`
    );
    return JSON.parse(value, (key, v) => {
      if (typeof v !== "string") {
        return v;
      }
      if (v === `${CHAR}NaN${CHAR}`) {
        return Number.NaN;
      }
      if (v === `${CHAR}Infinity${CHAR}`) {
        return Number.POSITIVE_INFINITY;
      }
      if (v === `${CHAR}-Infinity${CHAR}`) {
        return Number.NEGATIVE_INFINITY;
      }
      return v;
    }) as T;
  } catch {
    return {} as T;
  }
}

/**
 * Parse the initial value.
 * It will first check if the parent element is a <marimo-ui-element/> with an object-id that
 * exist in the UI registry.
 * And otherwise fallback to the data-initial-value attribute.
 */
export function parseInitialValue<T>(element: HTMLElement): T {
  // If parent is a <marimo-ui-element/> and has object-id, use that as the initialize the value
  const objectId = element.parentElement?.getAttribute("object-id");
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
