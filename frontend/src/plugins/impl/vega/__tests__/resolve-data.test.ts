/* Copyright 2024 Marimo. All rights reserved. */
import { afterEach, describe, expect, it, vi } from "vitest";
import { vegaLoader } from "../loader";
import { resolveVegaSpecData } from "../resolve-data";
import { VegaLiteSpec } from "../types";

function asSpec(spec: unknown): VegaLiteSpec {
  return spec as VegaLiteSpec;
}

describe("resolveVegaSpecData", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("returns the input spec if it is falsy", async () => {
    expect(await resolveVegaSpecData(null!)).toBeNull();
    expect(await resolveVegaSpecData(undefined!)).toBeUndefined();
  });

  it("returns the input spec if it has no data", async () => {
    const spec = asSpec({ someProperty: "value" });
    expect(await resolveVegaSpecData(spec)).toEqual(spec);
  });

  it("returns the input spec if the data does not contain a URL", async () => {
    const spec = asSpec({ data: { name: "dataset" } });
    expect(await resolveVegaSpecData(spec)).toEqual(spec);
  });

  it("returns the input spec if the URL in the data is invalid", async () => {
    const spec = asSpec({ data: { url: "invalidURL" } });
    vi.spyOn(vegaLoader, "load").mockRejectedValue(new Error("Invalid URL"));
    await expect(() => resolveVegaSpecData(spec)).rejects.toThrow(
      "Invalid URL",
    );
  });

  it("resolves the URL data and returns a new spec with the resolved data", async () => {
    const spec = asSpec({
      data: { url: "http://example.com/data", format: "json" },
    });
    const resolvedData = { some: "data" };
    vi.spyOn(vegaLoader, "load").mockResolvedValueOnce(resolvedData);

    const expected = {
      ...spec,
      data: {
        name: "/data",
      },
      datasets: {
        "/data": resolvedData,
      },
    } as unknown as VegaLiteSpec;

    await expect(resolveVegaSpecData(spec)).resolves.toEqual(expected);
    expect(vegaLoader.load).toHaveBeenCalledWith("http://example.com/data");
  });

  it("correctly resolves nested URL data in layers", async () => {
    const spec = asSpec({
      mark: "point",
      layer: [
        { data: { url: "http://example.com/data1", format: "json" } },
        { data: { url: "http://example.com/data2", format: "json" } },
      ],
    });
    const resolvedData1 = { some: "data1" };
    const resolvedData2 = { some: "data2" };
    vi.spyOn(vegaLoader, "load")
      .mockResolvedValueOnce(resolvedData1)
      .mockResolvedValueOnce(resolvedData2);

    const expected = {
      mark: "point",
      layer: [
        {
          data: { name: "/data1" },
        },
        {
          data: { name: "/data2" },
        },
      ],
      datasets: {
        "/data1": resolvedData1,
        "/data2": resolvedData2,
      },
    };

    await expect(resolveVegaSpecData(spec)).resolves.toEqual(expected);
    expect(vegaLoader.load).toHaveBeenCalledTimes(2);
  });

  it("correctly resolves nested URL data in hconcat and vconcat", async () => {
    const spec = asSpec({
      mark: "point",
      hconcat: [
        { data: { url: "http://example.com/data1", format: "json" } },
        { data: { url: "http://example.com/data2", format: "json" } },
      ],
      vconcat: [
        { data: { url: "http://example.com/data3", format: "json" } },
        { data: { url: "http://example.com/data4", format: "json" } },
      ],
    });
    const resolvedData1 = { some: "data1" };
    const resolvedData2 = { some: "data2" };
    const resolvedData3 = { some: "data3" };
    const resolvedData4 = { some: "data4" };
    vi.spyOn(vegaLoader, "load")
      .mockResolvedValueOnce(resolvedData1)
      .mockResolvedValueOnce(resolvedData2)
      .mockResolvedValueOnce(resolvedData3)
      .mockResolvedValueOnce(resolvedData4);

    const expected = {
      mark: "point",
      hconcat: [{ data: { name: "/data1" } }, { data: { name: "/data2" } }],
      vconcat: [{ data: { name: "/data3" } }, { data: { name: "/data4" } }],
      datasets: {
        "/data1": resolvedData1,
        "/data2": resolvedData2,
        "/data3": resolvedData3,
        "/data4": resolvedData4,
      },
    };

    await expect(resolveVegaSpecData(spec)).resolves.toEqual(expected);
    expect(vegaLoader.load).toHaveBeenCalledTimes(4);
  });
});
