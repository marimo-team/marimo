/* Copyright 2024 Marimo. All rights reserved. */
import { Marks } from "./marks";
import {
  AnyMark,
  EncodingType,
  Encodings,
  Field,
  MarkDef,
  SharedCompositeEncoding,
  VegaLiteSpec,
} from "./types";

/**
 * Vega has multiple types of encodings: x, y, color, size, etc.
 *
 * For all the non-xy encodings, we want to find all the fields that are encoded.
 * These are the encodings that are placed on the legend and thus selectable.
 */
export function findEncodedFields(spec: VegaLiteSpec): string[] {
  if (!spec || !("encoding" in spec)) {
    return [];
  }

  const { encoding } = spec;
  if (!encoding) {
    return [];
  }

  const encodings = Object.entries(encoding);

  // We need to find the field from:
  // "color": {
  //   "condition": {
  //     "field": "?",
  //     "type": "nominal",
  //     "test": {"and": [{"param": "select"}]}
  //   },
  //   "value": "grey"
  // },
  // OR
  // "size": {"field": "?", "type": "quantitative"},

  return encodings.flatMap((entry) => {
    const [key, encoding] = entry as [keyof Encodings, Encodings];
    if (!encoding) {
      return [];
    }
    if (!ALLOWED_ENCODING_TYPES.has(key as EncodingType)) {
      return [];
    }

    if ("field" in encoding && typeof encoding.field === "string") {
      return [encoding.field];
    }

    if (
      "condition" in encoding &&
      encoding.condition &&
      typeof encoding.condition === "object" &&
      "field" in encoding.condition &&
      encoding.condition.field &&
      typeof encoding.condition.field === "string"
    ) {
      return [encoding.condition.field];
    }

    return [];
  });
}

// We can add more encodings here if we want to support more
const ALLOWED_ENCODING_TYPES = new Set<EncodingType>([
  "color",
  "fill",
  "fillOpacity",
  "opacity",
  "shape",
  "size",
]);

export function makeEncodingInteractive(
  key: "opacity",
  encodings: SharedCompositeEncoding<Field>,
  paramNames: string[],
  mark: AnyMark | undefined,
): SharedCompositeEncoding<Field> {
  const test = {
    and: paramNames.map((paramName) => ({
      param: paramName,
    })),
  };

  switch (key) {
    // As of now, we only update opacity to signal selection
    case "opacity": {
      const initialOpacity = Marks.getOpacity(mark as MarkDef) || 1;
      return {
        ...encodings,
        opacity: {
          condition: {
            test: test,
            value: initialOpacity,
          },
          value: initialOpacity / 5, // 20% opacity
        },
      };
    }
    default:
      return encodings;
  }
}
