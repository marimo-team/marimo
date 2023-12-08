/* Copyright 2023 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { vegaLoadData, vegaLoader } from "../loader";

describe("vega loader", () => {
  it("should parse csv data", async () => {
    const csvData = `
active,username,id
2023-08-14T19:28:47Z,akshayka,1994308
2023-08-14T21:30:17Z,mscolnick,5108954
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const data = await vegaLoadData(csvData, { type: "csv", parse: "auto" });

    expect(data).toMatchInlineSnapshot(`
      [
        {
          "active": "2023-08-14T19:28:47.000Z",
          "id": 1994308,
          "username": "akshayka",
        },
        {
          "active": "2023-08-14T21:30:17.000Z",
          "id": 5108954,
          "username": "mscolnick",
        },
      ]
    `);
  });
});
