/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { COPILOT_MODES } from "@/core/config/config-schema";
import { FRONTEND_TOOL_REGISTRY, FrontendToolRegistry } from "../registry";
import { TestFrontendTool } from "../sample-tool";

// Tools that have these keys in their parameters are likely not supported by Google
// So we should be careful to add these types of schemas
const INVALID_KEYS_IN_SCHEMA_PARAMS = new Set(["anyOf", "oneOf"]);

describe("FrontendToolRegistry", () => {
  it("registers tools via constructor and supports has()", () => {
    const registry = new FrontendToolRegistry([new TestFrontendTool()]);
    expect(registry.has("test_frontend_tool")).toBe(true);
    expect(registry.has("nonexistent_tool" as string)).toBe(false);
  });

  it("invokes a tool with valid args and validates input/output", async () => {
    const registry = new FrontendToolRegistry([new TestFrontendTool()]);
    const response = await registry.invoke(
      "test_frontend_tool",
      {
        name: "Alice",
      },
      {} as never,
    );

    // Check InvokeResult wrapper
    expect(response.tool_name).toBe("test_frontend_tool");
    expect(response.error).toBeNull();

    // Check the actual tool output
    expect(response.result).toMatchObject({
      status: "success",
      data: {
        greeting: "Hello: Alice",
      },
      next_steps: expect.arrayContaining([expect.any(String)]),
    });

    // Verify timestamp is present and valid
    const output = response.result as { data: { timestamp: string } };
    expect(output.data.timestamp).toBeDefined();
    expect(typeof output.data.timestamp).toBe("string");
  });

  it("returns a structured error on invalid args", async () => {
    const registry = new FrontendToolRegistry([new TestFrontendTool()]);
    const response = await registry.invoke(
      "test_frontend_tool",
      {},
      {} as never,
    );

    // Check InvokeResult wrapper
    expect(response.tool_name).toBe("test_frontend_tool");
    expect(response.result).toBeNull();
    expect(response.error).toBeDefined();
    expect(typeof response.error).toBe("string");

    // Verify error message contains expected prefix
    expect(response.error).toMatchInlineSnapshot(
      `"Error invoking tool ToolExecutionError: {"message":"Tool test_frontend_tool returned invalid input: ✖ Invalid input: expected string, received undefined\\n  → at name","code":"INVALID_ARGUMENTS","is_retryable":true,"suggested_fix":"Please check the arguments and try again."}"`,
    );
  });

  it("returns tool schemas with expected shape and memoizes the result", () => {
    const registry = new FrontendToolRegistry([new TestFrontendTool()]);

    const schemas1 = registry.getToolSchemas("ask");
    expect(Array.isArray(schemas1)).toBe(true);
    expect(schemas1.length).toBe(1);

    const def = schemas1[0];
    expect(def.name).toBe("test_frontend_tool");
    expect(def.source).toBe("frontend");
    expect(def.mode).toEqual(["ask"]);
    expect(typeof def.description).toBe("string");

    const params = def.parameters as Record<string, unknown>;
    expect(params && typeof params === "object").toBe(true);
    const properties = (params as { properties?: Record<string, unknown> })
      .properties;
    expect(properties && typeof properties === "object").toBe(true);
    expect("name" in (properties ?? {})).toBe(true);

    const schemas2 = registry.getToolSchemas("ask");
    expect(schemas2).toBe(schemas1);

    // Should not include tools for other modes
    const schemas3 = registry.getToolSchemas("agent");
    expect(schemas3.length).toBe(0);
  });

  it("tool schemas should not contain invalid keys", () => {
    const registry = FRONTEND_TOOL_REGISTRY;

    function hasInvalidKeys(obj: unknown): boolean {
      if (obj && typeof obj === "object") {
        for (const [key, value] of Object.entries(obj)) {
          if (INVALID_KEYS_IN_SCHEMA_PARAMS.has(key)) {
            return true;
          }
          if (
            typeof value === "object" &&
            value !== null &&
            hasInvalidKeys(value)
          ) {
            return true;
          }
        }
      }
      return false;
    }

    for (const mode of COPILOT_MODES) {
      const schemas = registry.getToolSchemas(mode);
      for (const schema of schemas) {
        expect(hasInvalidKeys(schema.parameters)).toBe(false);
      }
    }
  });
});
