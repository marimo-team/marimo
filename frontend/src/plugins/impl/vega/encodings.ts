/* Copyright 2023 Marimo. All rights reserved. */
import {
  EncodingType,
  Encodings,
  Field,
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
  key: EncodingType,
  encodings: SharedCompositeEncoding<Field>,
  paramNames: string[]
): SharedCompositeEncoding<Field> {
  const test = {
    and: paramNames.map((paramName) => ({
      param: paramName,
    })),
  };

  switch (key) {
    // For most encodings, we want to update the opacity of the mark
    case "color":
    case "fill":
    case "fillOpacity":
    case "opacity":
    case "shape":
    case "size":
      return {
        ...encodings,
        opacity: {
          condition: {
            test: test,
            value: 1,
          },
          value: 0.2,
        },
      };
    default:
      return encodings;
  }
}
