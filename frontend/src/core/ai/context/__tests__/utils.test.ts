/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { contextToXml } from "../utils";

describe("contextToXml", () => {
  it("should convert basic context to XML", () => {
    const context = {
      type: "data",
      data: {
        name: "dataset1",
        source: "memory",
      },
    };

    const result = contextToXml(context);
    expect(result).toBe('<data name="dataset1" source="memory"></data>');
  });

  it("should handle context with details", () => {
    const context = {
      type: "variable",
      data: {
        name: "my_var",
        dataType: "string",
      },
      details: "This is a string variable",
    };

    const result = contextToXml(context);
    expect(result).toBe(
      '<variable name="my_var" dataType="string">This is a string variable</variable>',
    );
  });

  it("should escape XML characters in attributes", () => {
    const context = {
      type: "data",
      data: {
        name: "dataset<>&\"'",
        description: "Contains special chars",
      },
    };

    const result = contextToXml(context);
    expect(result).toMatchInlineSnapshot(
      `"<data name="dataset&lt;&gt;&"'" description="Contains special chars"></data>"`,
    );
  });

  it("should escape XML characters in details", () => {
    const context = {
      type: "error",
      data: {
        name: "error1",
      },
      details: "Error message with <tags> & \"quotes\" and 'apostrophes'",
    };

    const result = contextToXml(context);
    expect(result).toMatchInlineSnapshot(
      `"<error name="error1">Error message with &lt;tags&gt; & "quotes" and 'apostrophes'</error>"`,
    );
  });

  it("should handle undefined values in data", () => {
    const context = {
      type: "variable",
      data: {
        name: "my_var",
        dataType: undefined,
        value: "test",
      },
    };

    const result = contextToXml(context);
    expect(result).toBe('<variable name="my_var" value="test"></variable>');
  });

  it("should handle empty data object", () => {
    const context = {
      type: "empty",
      data: {},
    };

    const result = contextToXml(context);
    expect(result).toBe("<empty></empty>");
  });

  it("should handle numeric values", () => {
    const context = {
      type: "metric",
      data: {
        count: 42,
        percentage: 85.5,
        isActive: true,
      },
    };

    const result = contextToXml(context);
    expect(result).toBe(
      '<metric count="42" percentage="85.5" isActive="true"></metric>',
    );
  });

  it("should handle json string data", () => {
    const context = {
      type: "complex",
      data: {
        name: "test",
        config: JSON.stringify({ key: "value", nested: { prop: "test" } }),
      },
      details: "Complex configuration data",
    };

    const result = contextToXml(context);
    expect(result).toMatchInlineSnapshot(
      `"<complex name="test" config="{"key":"value","nested":{"prop":"test"}}">Complex configuration data</complex>"`,
    );
  });

  it("should handle objects", () => {
    const context = {
      type: "object",
      data: {
        name: "test",
        config: { key: "value", nested: { prop: "test" } },
      },
      details: "Complex configuration data",
    };

    const result = contextToXml(context);
    expect(result).toMatchInlineSnapshot(
      `"<object name="test" config="{"key":"value","nested":{"prop":"test"}}">Complex configuration data</object>"`,
    );
  });

  it("should handle arrays", () => {
    const context = {
      type: "array",
      data: {
        name: "test",
        array: [1, 2, 3],
      },
    };

    const result = contextToXml(context);
    expect(result).toMatchInlineSnapshot(
      `"<array name="test" array="[1,2,3]"></array>"`,
    );
  });

  it("should handle boolean values", () => {
    const context = {
      type: "flags",
      data: {
        enabled: true,
        visible: false,
      },
    };

    const result = contextToXml(context);
    expect(result).toBe('<flags enabled="true" visible="false"></flags>');
  });

  it("should handle null values", () => {
    const context = {
      type: "nullable",
      data: {
        name: "test",
        value: null,
      },
    };

    const result = contextToXml(context);
    expect(result).toBe('<nullable name="test" value="null"></nullable>');
  });

  it("should handle multiline details", () => {
    const context = {
      type: "multiline",
      data: {
        name: "test",
      },
      details: "Line 1\nLine 2\nLine 3",
    };

    const result = contextToXml(context);
    expect(result).toBe(
      '<multiline name="test">Line 1\nLine 2\nLine 3</multiline>',
    );
  });

  it("should handle special characters in type name", () => {
    const context = {
      type: "data-source",
      data: {
        name: "test",
      },
    };

    const result = contextToXml(context);
    expect(result).toBe('<data-source name="test"></data-source>');
  });
});
