/* Copyright 2026 Marimo. All rights reserved. */
import type * as Plotly from "plotly.js";
import { describe, expect, it } from "vitest";
import { createParser } from "../parse-from-template";

describe("createParser", () => {
  it("does not create a new parser when the template is the same", () => {
    const parser1 = createParser("template");
    const parser2 = parser1.update("template");
    expect(parser1).toBe(parser2);

    const parser3 = parser1.update("template1");
    expect(parser1).not.toBe(parser3);
  });

  it("should correctly parse data using the extracted key-selector pairs", () => {
    const hovertemplate =
      "Origin=%{customdata[1]}<br>Horsepower=%{x}<br>Miles_per_Gallon=%{y}<br>Weight_in_lbs=%{marker.size}<br>Name=%{customdata[0]}<extra></extra>";
    const parser = createParser(hovertemplate);
    const data = {
      customdata: ["Mustang", "USA"],
      x: "300",
      y: "30",
      "marker.size": "2000",
    } as unknown as Plotly.PlotDatum;
    const result = parser.parse(data);
    expect(result).toEqual({
      Origin: "USA",
      Horsepower: "300",
      Miles_per_Gallon: "30",
      Weight_in_lbs: "2000",
      Name: "Mustang",
    });
  });

  it("should handle hover templates with no key-selector pairs", () => {
    const hovertemplate = "No data available";
    const parser = createParser(hovertemplate);
    const data = {} as unknown as Plotly.PlotDatum;
    const result = parser.parse(data);
    expect(result).toEqual({});
  });

  it("should handle data with missing keys", () => {
    const hovertemplate =
      "Origin=%{customdata[1]}<br>Name=%{customdata[0]}<extra></extra>";
    const parser = createParser(hovertemplate);
    const data = {
      customdata: ["Mustang"], // Missing 'customdata[1]'
    } as unknown as Plotly.PlotDatum;
    const result = parser.parse(data);
    expect(result).toEqual({
      Origin: undefined, // 'customdata[1]' is missing, so the value is undefined
      Name: "Mustang",
    });
  });

  it("should handle data with nested keys", () => {
    const hovertemplate =
      "Model=%{car.model}<br>Year=%{car.year}<extra></extra>";
    const parser = createParser(hovertemplate);
    const data = {
      car: {
        model: "Mustang",
        year: "1964",
      },
    } as unknown as Plotly.PlotDatum;
    const result = parser.parse(data);
    expect(result).toEqual({
      Model: "Mustang",
      Year: "1964",
    });
  });

  it("should handle labels with special characters (brackets, parentheses, spaces)", () => {
    const hovertemplate =
      "Horsepower [ps]=%{x}<br>Miles per Gallon=%{y}<br>Weight (lbs)=%{marker.size}<extra></extra>";
    const parser = createParser(hovertemplate);
    const data = {
      x: "110",
      y: "20.6",
      "marker.size": "3000",
    } as unknown as Plotly.PlotDatum;
    const result = parser.parse(data);
    expect(result).toEqual({
      "Horsepower [ps]": "110",
      "Miles per Gallon": "20.6",
      "Weight (lbs)": "3000",
    });
  });
});
