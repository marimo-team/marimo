/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import {
  FunctionCall,
  FunctionArg,
  VariableDeclaration,
  Literal,
} from "../poet";

describe("Python Poet", () => {
  describe("Variable Declaration", () => {
    it("should create a variable declaration", () => {
      const declaration = new VariableDeclaration("x", "42");
      expect(declaration.toCode()).toBe("x = 42");
    });

    it("should handle nested code objects", () => {
      const inner = new VariableDeclaration("y", "42");
      const declaration = new VariableDeclaration("x", inner);
      expect(declaration.toCode()).toBe("x = y = 42");
    });
  });

  describe("Function Call", () => {
    it("should create a function call", () => {
      const call = new FunctionCall("print", [
        new FunctionArg("message", "'Hello, world!'"),
      ]);
      expect(call.toCode()).toBe("print(message='Hello, world!')");
    });

    it("should create a function call with a literal", () => {
      const call = new FunctionCall("print", {
        message: new Literal("Hello, world!"),
      });
      expect(call.toCode()).toBe("print(message='Hello, world!')");
    });

    it("should add arguments", () => {
      const call = new FunctionCall("sum", [new FunctionArg("a", "1")]).addArg(
        new FunctionArg("b", "2"),
      );
      expect(call.toCode()).toBe("sum(a=1, b=2)");
    });

    it("should chain method calls", () => {
      const call = new FunctionCall("df", []).chain("head", [
        new FunctionArg("n", "5"),
      ]);
      expect(call.toCode()).toBe("df().head(n=5)");
    });
  });

  describe("Altair Charts", () => {
    it("should create a basic bar chart", () => {
      const chart = new FunctionCall("alt.Chart", [
        new FunctionArg("data", "df"),
      ])
        .chain("mark_bar", [])
        .chain("encode", {
          x: new Literal("category:N"),
          y: new Literal("value:Q"),
        });

      expect(chart.toCode()).toMatchInlineSnapshot(
        `"alt.Chart(data=df).mark_bar().encode(x='category:N', y='value:Q')"`,
      );
    });

    it("should create a scatter plot with color and tooltip", () => {
      const chart = new FunctionCall(
        "alt.Chart",
        [new FunctionArg("data", "df")],
        true,
      )
        .chain("mark_circle", [])
        .chain("encode", [
          new FunctionArg("x", "'x:Q'"),
          new FunctionArg("y", "'y:Q'"),
          new FunctionArg("color", "'category:N'"),
          new FunctionArg("tooltip", "['category:N', 'x:Q', 'y:Q', 'size:Q']"),
        ])
        .chain("interactive", []);

      expect(chart.toCode()).toMatchInlineSnapshot(
        `
        "alt.Chart(data=df)
        .mark_circle()
        .encode(
            x='x:Q',
            y='y:Q',
            color='category:N',
            tooltip=['category:N', 'x:Q', 'y:Q', 'size:Q']
        )
        .interactive()"
      `,
      );
    });

    it("should create a layered chart", () => {
      const points = new FunctionCall(
        "alt.Chart",
        [new FunctionArg("data", "df")],
        true,
      )
        .chain("mark_point", [])
        .chain("encode", [
          new FunctionArg("x", "'x:Q'"),
          new FunctionArg("y", "'y:Q'"),
        ]);

      const line = new FunctionCall(
        "alt.Chart",
        [new FunctionArg("data", "df")],
        true,
      )
        .chain("mark_line", [])
        .chain("encode", [
          new FunctionArg("x", "'x:Q'"),
          new FunctionArg("y", "'y:Q'"),
        ]);

      const layered = new FunctionCall("alt.layer", [points, line], true).chain(
        "properties",
        [new FunctionArg("title", "'Layered Chart'")],
      );

      expect(layered.toCode()).toMatchInlineSnapshot(
        `
        "alt.layer(
            alt.Chart(data=df)
            .mark_point()
            .encode(
                x='x:Q',
                y='y:Q'
            ),
            alt.Chart(data=df)
            .mark_line()
            .encode(
                x='x:Q',
                y='y:Q'
            )
        )
        .properties(title='Layered Chart')"
      `,
      );
    });

    it("should create a faceted chart", () => {
      const chart = new FunctionCall(
        "alt.Chart",
        [new FunctionArg("data", "df")],
        true,
      )
        .chain("mark_bar", [])
        .chain("encode", [
          new FunctionArg("x", "'category:N'"),
          new FunctionArg("y", "'value:Q'"),
          new FunctionArg("color", "'category:N'"),
          new FunctionArg("row", "'group:N'"),
        ])
        .chain("properties", [
          new FunctionArg("title", "'Faceted Bar Chart'"),
          new FunctionArg("height", "150"),
        ]);

      expect(chart.toCode()).toMatchInlineSnapshot(`
        "alt.Chart(data=df)
        .mark_bar()
        .encode(
            x='category:N',
            y='value:Q',
            color='category:N',
            row='group:N'
        )
        .properties(
            title='Faceted Bar Chart',
            height=150
        )"
      `);
    });
  });
});
