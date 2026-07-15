/* Copyright 2026 Marimo. All rights reserved. */
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
  ISLANDS_JSON_SCRIPT_TYPE,
} from "@/core/islands/constants";
import { Logger } from "@/utils/Logger";
import {
  createMarimoFile,
  extractIslandCodeFromEmbed,
  parseIslandCode,
  parseIslandEditor,
  parseIslandElement,
  parseIslandElementsIntoApps,
  parseMarimoIslandApps,
  retainIslandSource,
} from "../parse";
import { createMockIslandElement, createMockIslands } from "./test-utils.tsx";

function createPayloadCell(
  overrides: Partial<{
    cellId: string;
    code: string;
    outputHtml: string;
    outputMimetype: string;
    reactive: boolean;
    displayCode: boolean;
    displayOutput: boolean;
  }> = {},
) {
  return {
    cellId: "cell-1",
    code: 'print("payload")',
    outputHtml: "<div>payload</div>",
    outputMimetype: "text/html",
    reactive: true,
    displayCode: false,
    displayOutput: true,
    ...overrides,
  };
}

function appendPayload(
  root: HTMLElement,
  payload: {
    schemaVersion: number;
    appId: string;
    cells: ReturnType<typeof createPayloadCell>[];
  },
) {
  const script = document.createElement("script");
  script.type = ISLANDS_JSON_SCRIPT_TYPE;
  script.textContent = JSON.stringify(payload);
  root.appendChild(script);
}

describe("createMarimoFile", () => {
  it("should return a string", () => {
    const app = {
      cells: [
        {
          code: 'print("Hello, World!")',
        },
      ],
    };
    const result = createMarimoFile(app);
    expect(typeof result).toBe("string");
  });

  it("should correctly format a single cell", () => {
    const app = {
      cells: [
        {
          code: 'print("Hello, World!")',
        },
      ],
    };
    const result = createMarimoFile(app);
    expect(result).toMatchInlineSnapshot(`
      "import marimo
      app = marimo.App()
      @app.cell
      def __():
          print("Hello, World!")
          return"
    `);
  });

  it("should correctly format multiple cells", () => {
    const app = {
      cells: [
        {
          code: 'print("Hello, World!")',
        },
        {
          code: 'print("Goodbye, World!")',
        },
      ],
    };
    const result = createMarimoFile(app);
    expect(result).toMatchInlineSnapshot(`
      "import marimo
      app = marimo.App()
      @app.cell
      def __():
          print("Hello, World!")
          return
      @app.cell
      def __():
          print("Goodbye, World!")
          return"
    `);
  });

  it("should create an async marimo file from cells", () => {
    const app = {
      cells: [{ code: "await asyncio.sleep(1)" }],
    };

    const result = createMarimoFile(app);

    expect(result).toMatchInlineSnapshot(`
      "import marimo
      app = marimo.App()
      @app.cell
      async def __():
          await asyncio.sleep(1)
          return"
    `);
  });

  it("should create disabled marimo cells", () => {
    const app = {
      cells: [{ code: "x = 0", disabled: true }, { code: "x = 1" }],
    };

    const result = createMarimoFile(app);

    expect(result).toMatchInlineSnapshot(`
      "import marimo
      app = marimo.App()
      @app.cell(disabled=True)
      def __():
          pass
          return
      @app.cell
      def __():
          x = 1
          return"
    `);
  });

  it("should properly indent multi-line code", () => {
    const app = {
      cells: [{ code: "if True:\n    print('hello')\n    print('world')" }],
    };

    const result = createMarimoFile(app);

    expect(result).toMatchInlineSnapshot(`
      "import marimo
      app = marimo.App()
      @app.cell
      def __():
          if True:
              print('hello')
              print('world')
          return"
    `);
  });
});

describe("parseIslandCode", () => {
  let codes = [
    `
  def __():
    print("Hello, World!")
    return
  `,
    `def __():\n    print("Hello, World!")\n    return`,
    `def __():
    print("Hello, World!")
    return`,
  ];

  codes = [...codes, ...codes.map(encodeURIComponent)];

  it.each(codes)(
    "should return the code without leading or trailing whitespace",
    (code) => {
      const result = parseIslandCode(code);
      const expected = 'def __():\n    print("Hello, World!")\n    return';
      expect(result).toBe(expected);
    },
  );

  it("should parse URI-encoded code with special characters", () => {
    const code = "print(%22Hello%2C%20world!%22)";

    const result = parseIslandCode(code);

    expect(result).toBe('print("Hello, world!")');
  });

  it("should handle null and undefined", () => {
    expect(parseIslandCode(null)).toBe("");
    expect(parseIslandCode(undefined)).toBe("");
  });
});

describe("parseIslandEditor", () => {
  it("should parse JSON-encoded code", () => {
    const code = '"print(\\"Hello\\")"';

    const result = parseIslandEditor(code);

    expect(result).toBe('print("Hello")');
  });

  it("should return raw code if JSON parsing fails", () => {
    const code = 'print("Hello")';

    const result = parseIslandEditor(code);

    expect(result).toBe('print("Hello")');
  });

  it("should handle null and undefined", () => {
    expect(parseIslandEditor(null)).toBe("");
    expect(parseIslandEditor(undefined)).toBe("");
  });
});

describe("extractIslandCodeFromEmbed", () => {
  it("should extract code from marimo-cell-code element", () => {
    const element = createMockIslandElement({
      code: 'print("test")',
    });
    element.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");

    const result = extractIslandCodeFromEmbed(element);

    expect(result).toBe('print("test")');
  });

  it("should return empty string for non-reactive cells", () => {
    const element = createMockIslandElement({
      code: 'print("test")',
    });
    element.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "false");

    const result = extractIslandCodeFromEmbed(element);

    expect(result).toBe("");
  });

  it("should extract code from editor element if code element not found", () => {
    const element = document.createElement(ISLAND_TAG_NAMES.ISLAND);
    element.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    const editor = document.createElement(ISLAND_TAG_NAMES.CODE_EDITOR);
    editor.setAttribute("data-initial-value", '"print(\\"hello\\")"');
    element.appendChild(editor);

    const result = extractIslandCodeFromEmbed(element);

    expect(result).toBe('print("hello")');
  });

  it("should return empty string if no code elements found", () => {
    const element = document.createElement(ISLAND_TAG_NAMES.ISLAND);
    element.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");

    const result = extractIslandCodeFromEmbed(element);

    expect(result).toBe("");
  });
});

describe("parseIslandElement", () => {
  it("should parse a valid island element", () => {
    const element = createMockIslandElement({
      code: 'print("test")',
      innerHTML: "<div>output</div>",
    });
    element.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");

    const result = parseIslandElement(element);

    expect(result).toMatchInlineSnapshot(`
      {
        "code": "print("test")",
        "output": "<div>output</div>",
      }
    `);
  });

  it("should return null if output is missing", () => {
    const element = document.createElement(ISLAND_TAG_NAMES.ISLAND);
    element.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    const codeElement = document.createElement(ISLAND_TAG_NAMES.CELL_CODE);
    codeElement.textContent = encodeURIComponent('print("test")');
    element.appendChild(codeElement);

    const result = parseIslandElement(element);

    expect(result).toBeNull();
  });

  it("should return null if code is missing", () => {
    const element = document.createElement(ISLAND_TAG_NAMES.ISLAND);
    const outputElement = document.createElement(ISLAND_TAG_NAMES.CELL_OUTPUT);
    outputElement.innerHTML = "<div>output</div>";
    element.appendChild(outputElement);

    const result = parseIslandElement(element);

    expect(result).toBeNull();
  });

  it("uses retained source after the custom element renders", () => {
    const element = document.createElement(ISLAND_TAG_NAMES.ISLAND);
    retainIslandSource(element, {
      code: 'print("retained")',
      output: "<div>retained output</div>",
    });

    expect(parseIslandElement(element)).toEqual({
      code: 'print("retained")',
      output: "<div>retained output</div>",
    });
  });

  it("prefers new live source when an island element is reused", () => {
    const element = createMockIslandElement({
      code: 'print("new")',
      innerHTML: "<div>new output</div>",
    });
    element.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    retainIslandSource(element, {
      code: 'print("retained")',
      output: "<div>retained output</div>",
    });

    expect(parseIslandElement(element)).toEqual({
      code: 'print("new")',
      output: "<div>new output</div>",
    });
  });
});

describe("parseIslandElementsIntoApps", () => {
  it("should parse single app with single cell", () => {
    const elements = [
      createMockIslandElement({
        appId: "app1",
        cellIdx: "0",
        code: 'print("hello")',
        innerHTML: "<div>output1</div>",
      }),
    ];
    elements[0].setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");

    const result = parseIslandElementsIntoApps(elements);

    expect(result).toHaveLength(1);
    expect(result).toMatchInlineSnapshot(`
      [
        {
          "cells": [
            {
              "code": "print("hello")",
              "idx": 0,
              "output": "<div>output1</div>",
            },
          ],
          "id": "app1",
        },
      ]
    `);
  });

  it("should parse single app with multiple cells", () => {
    const elements = createMockIslands(3, "app1").map((el) => {
      el.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      return el;
    });

    const result = parseIslandElementsIntoApps(elements);

    expect(result).toHaveLength(1);
    expect(result).toMatchInlineSnapshot(`
      [
        {
          "cells": [
            {
              "code": "cell_0 = 0",
              "idx": 0,
              "output": "<div>output 0</div>",
            },
            {
              "code": "cell_1 = 1",
              "idx": 1,
              "output": "<div>output 1</div>",
            },
            {
              "code": "cell_2 = 2",
              "idx": 2,
              "output": "<div>output 2</div>",
            },
          ],
          "id": "app1",
        },
      ]
    `);
  });

  it("should parse multiple apps", () => {
    const elements = [
      ...createMockIslands(2, "app1"),
      ...createMockIslands(2, "app2"),
    ].map((el) => {
      el.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      return el;
    });

    const result = parseIslandElementsIntoApps(elements);

    expect(result).toHaveLength(2);
    expect(result).toMatchInlineSnapshot(`
      [
        {
          "cells": [
            {
              "code": "cell_0 = 0",
              "idx": 0,
              "output": "<div>output 0</div>",
            },
            {
              "code": "cell_1 = 1",
              "idx": 1,
              "output": "<div>output 1</div>",
            },
          ],
          "id": "app1",
        },
        {
          "cells": [
            {
              "code": "cell_0 = 0",
              "idx": 0,
              "output": "<div>output 0</div>",
            },
            {
              "code": "cell_1 = 1",
              "idx": 1,
              "output": "<div>output 1</div>",
            },
          ],
          "id": "app2",
        },
      ]
    `);
  });

  it("should skip elements without app-id", () => {
    const validElement = createMockIslandElement({
      appId: "app1",
      code: 'print("test")',
      innerHTML: "<div>output</div>",
    });
    validElement.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");

    const invalidElement = document.createElement(ISLAND_TAG_NAMES.ISLAND);
    invalidElement.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");

    const result = parseIslandElementsIntoApps([validElement, invalidElement]);

    expect(result).toHaveLength(1);
    expect(result).toMatchInlineSnapshot(`
      [
        {
          "cells": [
            {
              "code": "print("test")",
              "idx": 0,
              "output": "<div>output</div>",
            },
          ],
          "id": "app1",
        },
      ]
    `);
  });

  it("should assign correct cell indices", () => {
    const elements = createMockIslands(3, "app1").map((el) => {
      el.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      return el;
    });

    const result = parseIslandElementsIntoApps(elements);

    expect(result).toMatchInlineSnapshot(`
      [
        {
          "cells": [
            {
              "code": "cell_0 = 0",
              "idx": 0,
              "output": "<div>output 0</div>",
            },
            {
              "code": "cell_1 = 1",
              "idx": 1,
              "output": "<div>output 1</div>",
            },
            {
              "code": "cell_2 = 2",
              "idx": 2,
              "output": "<div>output 2</div>",
            },
          ],
          "id": "app1",
        },
      ]
    `);
  });

  it("should set data-cell-idx attribute on elements", () => {
    const elements = createMockIslands(2, "app1").map((el) => {
      el.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      return el;
    });

    parseIslandElementsIntoApps(elements);

    expect(elements[0].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
    expect(elements[1].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("1");
  });
});

describe("parseMarimoIslandApps", () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
    vi.restoreAllMocks();
  });

  it("should parse islands from document", () => {
    const elements = createMockIslands(2, "app1").map((el) => {
      el.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      return el;
    });
    for (const el of elements) {
      container.appendChild(el);
    }

    const result = parseMarimoIslandApps(container);

    expect(result).toHaveLength(1);
    expect(result).toMatchInlineSnapshot(`
      [
        {
          "cells": [
            {
              "code": "cell_0 = 0",
              "idx": 0,
              "output": "<div>output 0</div>",
            },
            {
              "code": "cell_1 = 1",
              "idx": 1,
              "output": "<div>output 1</div>",
            },
          ],
          "id": "app1",
        },
      ]
    `);
  });

  it("should return empty array if no islands found", () => {
    const result = parseMarimoIslandApps(container);

    expect(result).toEqual([]);
  });

  it("should accept custom root element", () => {
    const customRoot = document.createElement("div");
    const elements = createMockIslands(1, "app1").map((el) => {
      el.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      return el;
    });
    for (const el of elements) {
      customRoot.appendChild(el);
    }

    const result = parseMarimoIslandApps(customRoot);

    expect(result).toHaveLength(1);
    expect(result).toMatchInlineSnapshot(`
      [
        {
          "cells": [
            {
              "code": "cell_0 = 0",
              "idx": 0,
              "output": "<div>output 0</div>",
            },
          ],
          "id": "app1",
        },
      ]
    `);
  });

  it("should use supported JSON payload data for matched islands", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: 'print("dom")',
      innerHTML: "<div>dom</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [createPayloadCell()],
    });

    const result = parseMarimoIslandApps(container);

    expect(result).toEqual([
      {
        id: "app1",
        payloadBacked: true,
        cells: [
          {
            cellId: "cell-1",
            code: 'print("payload")',
            idx: 0,
            output: "<div>payload</div>",
          },
        ],
      },
    ]);
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID)).toBeNull();
    expect(extractIslandCodeFromEmbed(island)).toBe('print("payload")');
    expect(island.querySelector(ISLAND_TAG_NAMES.CELL_OUTPUT)?.innerHTML).toBe(
      "<div>payload</div>",
    );
  });

  it("preserves payload-backed cells after a non-materializing capability probe", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-2",
      code: "dom_code = True",
      innerHTML: "<div>dom output</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [createPayloadCell({ cellId: "cell-2" })],
    });
    const originalIsland = island.outerHTML;

    const probed = parseMarimoIslandApps(container, { materialize: false });

    expect(probed).toHaveLength(1);
    expect(island.outerHTML).toBe(originalIsland);

    expect(parseMarimoIslandApps(container)).toEqual(probed);
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID)).toBeNull();
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
  });

  it("keeps a payload anchor stable during duplicate initialization", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: "dom_code = True",
      innerHTML: "<div>dom output</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [createPayloadCell()],
    });

    const first = parseMarimoIslandApps(container);
    island.replaceChildren();
    const second = parseMarimoIslandApps(container);

    expect(second).toEqual(first);
    expect(island.childNodes).toHaveLength(0);
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
  });

  it("should parse Python-generated island payload snapshots", () => {
    const html = readFileSync(
      new URL(
        "../../../../../tests/_islands/snapshots/html-payload.txt",
        import.meta.url,
      ).pathname.replace(/^\/@fs/, ""),
      "utf8",
    );
    container.innerHTML = html;

    const result = parseMarimoIslandApps(container);
    const islands = container.querySelectorAll<HTMLElement>(
      ISLAND_TAG_NAMES.ISLAND,
    );

    expect(result).toEqual([
      {
        id: "main",
        payloadBacked: true,
        cells: [
          {
            cellId: "Hbol",
            code: "import marimo as mo",
            idx: 0,
            output: "",
          },
          {
            cellId: "MJUe",
            code: "mo.md('Hello, HTML!')",
            idx: 1,
            output: "",
          },
        ],
      },
    ]);
    expect(islands[0].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBeNull();
    expect(islands[1].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
    expect(islands[2].getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("1");
  });

  it("should fall back to DOM islands for unsupported payload versions", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: 'print("dom")',
      innerHTML: "<div>dom</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 2,
      appId: "app1",
      cells: [createPayloadCell()],
    });

    const result = parseMarimoIslandApps(container);

    expect(result).toEqual([
      {
        id: "app1",
        cells: [
          {
            code: 'print("dom")',
            idx: 0,
            output: "<div>dom</div>",
          },
        ],
      },
    ]);
  });

  it("should ignore payload scripts rendered inside island output", () => {
    const nestedPayload = {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          code: "payload_code_should_not_run = True",
          outputHtml: "<div>payload</div>",
        }),
      ],
    };
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: 'print("dom")',
      innerHTML: `<div>dom</div><script type="${ISLANDS_JSON_SCRIPT_TYPE}">${JSON.stringify(nestedPayload)}</script>`,
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);

    const result = parseMarimoIslandApps(container);

    expect(result).toEqual([
      {
        id: "app1",
        cells: [
          {
            code: 'print("dom")',
            idx: 0,
            output: island.querySelector(ISLAND_TAG_NAMES.CELL_OUTPUT)
              ?.innerHTML,
          },
        ],
      },
    ]);
  });

  it("should use payload order for runtime cell indices", () => {
    const second = createMockIslandElement({
      appId: "app1",
      cellId: "cell-2",
      code: "second_dom = True",
      innerHTML: "<div>second dom</div>",
    });
    const first = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: "first_dom = True",
      innerHTML: "<div>first dom</div>",
    });
    for (const island of [second, first]) {
      island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      container.appendChild(island);
    }
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          cellId: "cell-1",
          code: "first_payload = True",
          outputHtml: "<div>first payload</div>",
        }),
        createPayloadCell({
          cellId: "cell-2",
          code: "second_payload = True",
          outputHtml: "<div>second payload</div>",
        }),
      ],
    });

    const result = parseMarimoIslandApps(container);

    expect(result[0].cells.map((cell) => cell.code)).toEqual([
      "first_payload = True",
      "second_payload = True",
    ]);
    expect(first.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
    expect(second.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("1");
  });

  it("should include payload-only runtime cells", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-2",
      code: "value",
      innerHTML: "<div>value</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          cellId: "cell-1",
          code: "import marimo as mo",
          outputHtml: "",
        }),
        createPayloadCell({
          cellId: "cell-2",
          code: "mo.md('visible')",
          outputHtml: "<div>visible</div>",
        }),
      ],
    });

    const result = parseMarimoIslandApps(container);

    expect(result[0].cells.map((cell) => cell.code)).toEqual([
      "import marimo as mo",
      "mo.md('visible')",
    ]);
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("1");
  });

  it("should bind payload-backed islands by runtime index after static cells", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-2",
      code: "visible_dom = True",
      innerHTML: "<div>visible dom</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          cellId: "cell-1",
          code: "",
          outputHtml: "<div>static</div>",
          reactive: false,
        }),
        createPayloadCell({
          cellId: "cell-2",
          code: "visible_payload = True",
          outputHtml: "<div>visible payload</div>",
        }),
      ],
    });

    const result = parseMarimoIslandApps(container);

    expect(result[0].cells).toEqual([
      {
        cellId: "cell-1",
        code: "",
        disabled: true,
        idx: 0,
        output: "<div>static</div>",
      },
      {
        cellId: "cell-2",
        code: "visible_payload = True",
        idx: 1,
        output: "<div>visible payload</div>",
      },
    ]);
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("1");
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID)).toBeNull();
  });

  it("should fall back to DOM when no payload cell matches an island", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "dom-only",
      code: "dom_only = True",
      innerHTML: "<div>dom only</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    island.removeAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX);
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          cellId: "payload-only",
          code: "payload_only = True",
          outputHtml: "<div>payload only</div>",
        }),
      ],
    });

    const result = parseMarimoIslandApps(container);

    expect(result).toEqual([
      {
        id: "app1",
        cells: [
          {
            code: "dom_only = True",
            idx: 0,
            output: "<div>dom only</div>",
          },
        ],
      },
    ]);
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID)).toBe(
      "dom-only",
    );
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE)).toBe("true");
  });

  it("should ignore payloads without matching islands", () => {
    const warn = vi.spyOn(Logger, "warn").mockImplementation(() => undefined);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [createPayloadCell()],
    });

    const result = parseMarimoIslandApps(container);

    expect(result).toEqual([]);
    expect(warn).toHaveBeenCalledWith("No embedded marimo apps found.");
  });

  it("should still parse DOM-only apps when another app has payload", () => {
    const payloadIsland = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: "payload_dom = True",
      innerHTML: "<div>payload dom</div>",
    });
    const domIsland = createMockIslandElement({
      appId: "app2",
      code: "dom_app = True",
      innerHTML: "<div>dom app</div>",
    });
    for (const island of [payloadIsland, domIsland]) {
      island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      container.appendChild(island);
    }
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [createPayloadCell()],
    });

    const result = parseMarimoIslandApps(container);

    expect(result.map((app) => app.id)).toEqual(["app1", "app2"]);
    expect(result[0].cells[0].code).toBe('print("payload")');
    expect(result[1].cells[0].code).toBe("dom_app = True");
  });

  it("should materialize non-reactive payload islands without runtime cells", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: "static_dom = True",
      innerHTML: "<div>static dom</div>",
    });
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "false");
    island.removeAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX);
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          code: "",
          outputHtml: "<div>static payload</div>",
          reactive: false,
        }),
      ],
    });

    const result = parseMarimoIslandApps(container);

    expect(result).toEqual([]);
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBeNull();
    expect(island.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID)).toBeNull();
    expect(island.querySelector(ISLAND_TAG_NAMES.CELL_OUTPUT)?.innerHTML).toBe(
      "<div>static payload</div>",
    );
  });

  it("should keep non-reactive display code out of runtime cells", () => {
    const staticIsland = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: "x = 0",
      innerHTML: "<div>static</div>",
    });
    const reactiveIsland = createMockIslandElement({
      appId: "app1",
      cellId: "cell-2",
      code: "y = 1",
      innerHTML: "<div>reactive</div>",
    });
    staticIsland.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "false");
    reactiveIsland.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.append(staticIsland, reactiveIsland);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          cellId: "cell-1",
          code: "x = 0",
          outputHtml: "<div>static payload</div>",
          reactive: false,
          displayCode: true,
        }),
        createPayloadCell({
          cellId: "cell-2",
          code: "y = 1",
          outputHtml: "<div>reactive payload</div>",
        }),
      ],
    });

    const result = parseMarimoIslandApps(container);
    const file = createMarimoFile(result[0]);

    expect(result[0].cells).toEqual([
      {
        cellId: "cell-1",
        code: "",
        disabled: true,
        idx: 0,
        output: "<div>static payload</div>",
      },
      {
        cellId: "cell-2",
        code: "y = 1",
        idx: 1,
        output: "<div>reactive payload</div>",
      },
    ]);
    expect(file).not.toContain("x = 0");
    expect(file).toContain("@app.cell(disabled=True)\ndef __():\n    pass");
    expect(reactiveIsland.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe(
      "1",
    );
  });

  it("should update editor initial values from payload code", () => {
    const island = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: 'print("dom")',
      innerHTML: "<div>dom</div>",
    });
    island.insertAdjacentHTML(
      "beforeend",
      '<div data-marimo-element><marimo-code-editor data-initial-value="\\"print(\\\\\\"dom\\\\\\")\\""></marimo-code-editor></div>',
    );
    island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
    container.appendChild(island);
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [createPayloadCell()],
    });

    parseMarimoIslandApps(container);

    expect(
      island
        .querySelector(ISLAND_TAG_NAMES.CODE_EDITOR)
        ?.getAttribute("data-initial-value"),
    ).toBe(JSON.stringify('print("payload")'));
  });

  it("should match duplicate cell ids by occurrence", () => {
    const first = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: "dom_first = True",
      innerHTML: "<div>dom first</div>",
    });
    const second = createMockIslandElement({
      appId: "app1",
      cellId: "cell-1",
      code: "dom_second = True",
      innerHTML: "<div>dom second</div>",
    });
    for (const island of [first, second]) {
      island.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "true");
      container.appendChild(island);
    }
    appendPayload(container, {
      schemaVersion: 1,
      appId: "app1",
      cells: [
        createPayloadCell({
          code: "payload_first = True",
          outputHtml: "<div>payload first</div>",
        }),
        createPayloadCell({
          code: "payload_second = True",
          outputHtml: "<div>payload second</div>",
        }),
      ],
    });

    const result = parseMarimoIslandApps(container);

    expect(result[0].cells.map((cell) => cell.code)).toEqual([
      "payload_first = True",
      "payload_second = True",
    ]);
    expect(first.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("0");
    expect(second.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX)).toBe("1");
  });
});
