/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { findEncodedFields, makeEncodingInteractive } from "../encodings";
import { EncodingType, Encodings, VegaLiteSpec } from "../types";

describe("findEncodedFields", () => {
  it("should return an empty array when spec is undefined", () => {
    expect(findEncodedFields(undefined!)).toEqual([]);
  });

  it("should return an empty array when encoding is not in spec", () => {
    expect(findEncodedFields({} as VegaLiteSpec)).toEqual([]);
  });

  it("should return an array of fields that are encoded", () => {
    const spec = {
      mark: "point",
      encoding: {
        color: {
          field: "colorField",
          type: "nominal",
        },
        size: {
          field: "sizeField",
          type: "quantitative",
        },
      },
    } as VegaLiteSpec;

    expect(findEncodedFields(spec)).toEqual(["colorField", "sizeField"]);
  });

  it("should return an array of fields that are encoded in condition", () => {
    const spec = {
      encoding: {
        color: {
          condition: {
            field: "colorField",
            type: "nominal",
            test: { and: [{ param: "select" }] },
          },
          value: "grey",
        },
        size: {
          field: "sizeField",
          type: "quantitative",
        },
      },
    } as VegaLiteSpec;

    expect(findEncodedFields(spec)).toEqual(["colorField", "sizeField"]);
  });

  it("should return an empty array when encoding type is not allowed", () => {
    const spec = {
      encoding: {
        x: {
          field: "xField",
          type: "quantitative",
        },
        y: {
          field: "yField",
          type: "quantitative",
        },
      },
    } as VegaLiteSpec;

    expect(findEncodedFields(spec)).toEqual([]);
  });
});

describe("makeEncodingInteractive", () => {
  it.each([
    "color",
    "fill",
    "fillOpacity",
    "opacity",
    "shape",
    "size",
  ] as EncodingType[])("should return updated encodings for %s", (type) => {
    const encodings: Encodings = {
      [type]: {
        field: "someField",
        type: "quantitative",
      },
    };

    const expected = {
      ...encodings,
      opacity: {
        condition: {
          test: {
            and: [{ param: "param1" }],
          },
          value: 1,
        },
        value: 0.2,
      },
    };

    expect(
      makeEncodingInteractive("opacity", encodings, ["param1"], "point"),
    ).toEqual(expected);
  });

  it("should use a factor of the given opacity", () => {
    const encodings: Encodings = {
      x: {
        field: "someField",
        type: "quantitative",
      },
    };

    expect(
      makeEncodingInteractive("opacity", encodings, ["param1"], {
        type: "point",
        opacity: 0.6,
      }),
    ).toMatchInlineSnapshot(`
      {
        "opacity": {
          "condition": {
            "test": {
              "and": [
                {
                  "param": "param1",
                },
              ],
            },
            "value": 0.6,
          },
          "value": 0.12,
        },
        "x": {
          "field": "someField",
          "type": "quantitative",
        },
      }
    `);
  });

  it("should return updated encodings for multiple parameters", () => {
    const encodings: Encodings = {
      opacity: {
        field: "someField",
        type: "quantitative",
      },
    };

    const expected = {
      ...encodings,
      opacity: {
        condition: {
          test: {
            and: [{ param: "param1" }, { param: "param2" }],
          },
          value: 1,
        },
        value: 0.2,
      },
    };

    expect(
      makeEncodingInteractive(
        "opacity",
        encodings,
        ["param1", "param2"],
        "point",
      ),
    ).toEqual(expected);
  });
});
