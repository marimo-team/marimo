/* Copyright 2024 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
} from "@/core/islands/constants";
import {
  createMarimoFile,
  extractIslandCodeFromEmbed,
  parseIslandCode,
  parseIslandEditor,
  parseIslandElement,
  parseIslandElementsIntoApps,
  parseMarimoIslandApps,
} from "../parse";
import { createMockIslandElement, createMockIslands } from "./test-utils.tsx";

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
});
