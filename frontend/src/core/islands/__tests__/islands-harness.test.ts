/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, describe, expect, it } from "vitest";
import { ISLAND_DATA_ATTRIBUTES } from "@/core/islands/constants";
import {
  extractIslandCodeFromEmbed,
  parseIslandElement,
  parseIslandElementsIntoApps,
  parseMarimoIslandApps,
} from "../parse";
import {
  buildIslandHTML,
  createIslandHarness,
  type IslandHarness,
} from "./test-utils.tsx";

let harness: IslandHarness;

afterEach(() => {
  harness?.cleanup();
});

// ============================================================================
// Reactive vs Non-Reactive Parsing
// ============================================================================

describe("reactive vs non-reactive islands", () => {
  it("should parse reactive islands into apps with code", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: "x = 1", output: "<div>1</div>" },
        { reactive: true, code: "y = 2", output: "<div>2</div>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps).toHaveLength(1);
    expect(apps[0].cells).toHaveLength(2);
    expect(apps[0].cells[0].code).toBe("x = 1");
    expect(apps[0].cells[1].code).toBe("y = 2");
  });

  it("should skip non-reactive islands during parsing (no code sent to kernel)", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: "x = 1", output: "<div>1</div>" },
        { reactive: false, output: "<div>static content</div>" },
        { reactive: true, code: "y = 2", output: "<div>2</div>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps).toHaveLength(1);
    // Only the 2 reactive islands become cells
    expect(apps[0].cells).toHaveLength(2);
    expect(apps[0].cells[0].code).toBe("x = 1");
    expect(apps[0].cells[1].code).toBe("y = 2");
  });

  it("should not set data-cell-idx on non-reactive islands", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: "x = 1", output: "<div>1</div>" },
        { reactive: false, output: "<div>static</div>" },
      ]),
    );

    parseMarimoIslandApps(harness.container);

    const [reactiveIsland, nonReactiveIsland] = harness.islands;

    // Reactive island gets a cell index
    expect(reactiveIsland.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe(
      "0",
    );
    // Non-reactive island does NOT get a cell index
    expect(
      nonReactiveIsland.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX),
    ).toBeNull();
  });

  it("should handle all-non-reactive islands (empty app list)", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: false, output: "<div>static 1</div>" },
        { reactive: false, output: "<div>static 2</div>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps).toHaveLength(0);
  });
});

// ============================================================================
// extractIslandCodeFromEmbed
// ============================================================================

describe("extractIslandCodeFromEmbed with harness", () => {
  it("should return code for reactive islands", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: 'mo.md("hello")', output: "<div>hello</div>" },
      ]),
    );

    const code = extractIslandCodeFromEmbed(harness.islands[0]);
    expect(code).toBe('mo.md("hello")');
  });

  it("should return empty string for non-reactive islands", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        {
          reactive: false,
          code: 'mo.md("hello")',
          output: "<div>hello</div>",
        },
      ]),
    );

    const code = extractIslandCodeFromEmbed(harness.islands[0]);
    expect(code).toBe("");
  });
});

// ============================================================================
// parseIslandElement
// ============================================================================

describe("parseIslandElement with harness", () => {
  it("should return cell data for reactive island with output and code", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: "x = 1", output: "<div>1</div>" },
      ]),
    );

    const result = parseIslandElement(harness.islands[0]);
    expect(result).not.toBeNull();
    expect(result!.code).toBe("x = 1");
    expect(result!.output).toBe("<div>1</div>");
  });

  it("should return null for non-reactive island (code is empty)", () => {
    harness = createIslandHarness(
      buildIslandHTML([{ reactive: false, output: "<div>static</div>" }]),
    );

    const result = parseIslandElement(harness.islands[0]);
    expect(result).toBeNull();
  });
});

// ============================================================================
// Multi-app parsing
// ============================================================================

describe("multi-app parsing with harness", () => {
  it("should group islands by app-id", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { appId: "app-1", reactive: true, code: "a = 1", output: "<div/>" },
        { appId: "app-2", reactive: true, code: "b = 2", output: "<div/>" },
        { appId: "app-1", reactive: true, code: "c = 3", output: "<div/>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps).toHaveLength(2);

    const app1 = apps.find((a) => a.id === "app-1")!;
    const app2 = apps.find((a) => a.id === "app-2")!;

    expect(app1.cells).toHaveLength(2);
    expect(app1.cells[0].code).toBe("a = 1");
    expect(app1.cells[1].code).toBe("c = 3");

    expect(app2.cells).toHaveLength(1);
    expect(app2.cells[0].code).toBe("b = 2");
  });

  it("should assign sequential cell indices within each app", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { appId: "app-1", reactive: true, code: "a", output: "<div/>" },
        { appId: "app-1", reactive: true, code: "b", output: "<div/>" },
        { appId: "app-1", reactive: true, code: "c", output: "<div/>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps[0].cells.map((c) => c.idx)).toEqual([0, 1, 2]);
  });

  it("should skip non-reactive islands in cell index assignment", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: "a = 1", output: "<div/>" },
        { reactive: false, output: "<div>static</div>" },
        { reactive: true, code: "b = 2", output: "<div/>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps[0].cells).toHaveLength(2);
    expect(apps[0].cells[0].idx).toBe(0);
    expect(apps[0].cells[1].idx).toBe(1);

    // Verify DOM: reactive islands get indices, non-reactive does not
    expect(
      harness.islands[0].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX),
    ).toBe("0");
    expect(
      harness.islands[1].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX),
    ).toBeNull();
    expect(
      harness.islands[2].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX),
    ).toBe("1");
  });
});

// ============================================================================
// Mixed reactive/non-reactive scenarios (regression tests)
// ============================================================================

describe("mixed reactive/non-reactive island scenarios", () => {
  it("should handle the generate.py demo pattern: reactive + non-reactive + display_code", () => {
    // Mirrors the "Island Features" section of generate.py
    harness = createIslandHarness(
      buildIslandHTML([
        // Section header (reactive)
        {
          reactive: true,
          code: 'mo.md("## Display Code")',
          output: "<div><h2>Display Code</h2></div>",
        },
        // display_code island (reactive)
        {
          reactive: true,
          code: 'mo.md("You can show the code")',
          output: "<div>You can show the code</div>",
          displayCode: true,
        },
        // Non-reactive section header
        {
          reactive: true,
          code: 'mo.md("## Non-Reactive Islands")',
          output: "<div><h2>Non-Reactive Islands</h2></div>",
        },
        // Non-reactive island — the one that was crashing
        {
          reactive: false,
          code: 'mo.md("This island is non-reactive")',
          output:
            "<div>This island is non-reactive - it runs once and doesn't update</div>",
        },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);

    // Only 3 reactive islands become cells
    expect(apps).toHaveLength(1);
    expect(apps[0].cells).toHaveLength(3);

    // Non-reactive island (index 3) has no cell-idx
    expect(
      harness.islands[3].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX),
    ).toBeNull();
    expect(
      harness.islands[3].getAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE),
    ).toBe("false");
  });

  it("should handle non-reactive island at the start", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: false, output: "<div>static header</div>" },
        { reactive: true, code: "x = 1", output: "<div>1</div>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps).toHaveLength(1);
    expect(apps[0].cells).toHaveLength(1);
    expect(apps[0].cells[0].code).toBe("x = 1");
    expect(apps[0].cells[0].idx).toBe(0);

    // First island (non-reactive) has no index
    expect(
      harness.islands[0].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX),
    ).toBeNull();
    // Second island (reactive) gets index 0
    expect(
      harness.islands[1].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX),
    ).toBe("0");
  });

  it("should handle alternating reactive and non-reactive islands", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: "a = 1", output: "<div/>" },
        { reactive: false, output: "<div>static</div>" },
        { reactive: true, code: "b = 2", output: "<div/>" },
        { reactive: false, output: "<div>static</div>" },
        { reactive: true, code: "c = 3", output: "<div/>" },
      ]),
    );

    const apps = parseMarimoIslandApps(harness.container);
    expect(apps[0].cells).toHaveLength(3);
    expect(apps[0].cells.map((c) => c.code)).toEqual([
      "a = 1",
      "b = 2",
      "c = 3",
    ]);
    expect(apps[0].cells.map((c) => c.idx)).toEqual([0, 1, 2]);
  });
});

// ============================================================================
// parseIslandElementsIntoApps (direct element-level tests)
// ============================================================================

describe("parseIslandElementsIntoApps with mixed elements", () => {
  it("should preserve DOM order for cell indices", () => {
    harness = createIslandHarness(
      buildIslandHTML([
        { reactive: true, code: "first", output: "<div/>" },
        { reactive: true, code: "second", output: "<div/>" },
        { reactive: true, code: "third", output: "<div/>" },
      ]),
    );

    const apps = parseIslandElementsIntoApps(harness.islands);
    expect(apps[0].cells.map((c) => c.code)).toEqual([
      "first",
      "second",
      "third",
    ]);
  });

  it("should handle empty container", () => {
    harness = createIslandHarness("");
    const apps = parseMarimoIslandApps(harness.container);
    expect(apps).toHaveLength(0);
  });
});
