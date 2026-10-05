/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { DownloadAsSchema, GetExportMetadataSchema } from "../schemas";

describe("geometry export contracts", () => {
  it.each([undefined, "geom_b", ""])(
    "accepts a GeoJSON request with geometry %s",
    (geometry_column) => {
      const request = { format: "geojson", geometry_column };
      expect(DownloadAsSchema.input.parse(request)).toEqual(request);
    },
  );

  it("accepts a missing CRS response for an unnamed geometry", () => {
    const response = {
      url: "",
      filename: "",
      code: "missing_crs",
      column: "",
      error: "Declare a CRS.",
    };
    expect(DownloadAsSchema.output.parse(response)).toEqual(response);
  });

  it("accepts GeoJSON support when the default geometry has no CRS", () => {
    const metadata = {
      geometry_columns: [
        { name: "", encoding: "objects", crs: null },
        { name: "alternate", encoding: "objects", crs: "EPSG:4326" },
      ],
      primary_geometry_column: "",
      default_geometry_column: "",
      formats: {
        geojson: { available: true, reason: null, missing_packages: [] },
        parquet: {
          available: false,
          reason: "GeoParquet export requires pyarrow.",
          missing_packages: ["pyarrow"],
        },
      },
    };
    expect(GetExportMetadataSchema.output.parse(metadata)).toEqual(metadata);
  });
});
