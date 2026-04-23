/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { JsonOutput } from "../JsonOutput";

// Mock window.matchMedia for JsonViewer
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe("JsonOutput with enhanced mimetype handling", () => {
  it("should render data with various mimetypes without crashing", () => {
    const data = {
      text: "text/plain:Hello",
      html: "text/html:<strong>Bold</strong>",
      img: "image/png:data:image/png;base64,xyz...",
      set: "text/plain+set:[1,2,3]",
      tuple: "text/plain+tuple:[10,20]",
      custom: "application/custom:data",
      number: 42,
      boolean: true,
    };

    const { container } = render(<JsonOutput data={data} format="auto" />);

    // Verify component renders without crashing
    expect(container).toBeInTheDocument();
    expect(container.querySelector(".marimo-json-output")).toBeInTheDocument();
  });

  it("renders encoded non-string keys with Python-style affordances", () => {
    // Server-side `_key_formatter` encodes non-string dict keys with
    // mimetype prefixes; the frontend `keyRenderer` must decode them
    // so users see the original Python types (unquoted ints, parens for
    // tuples, etc.) instead of the raw encoded strings.
    const data = {
      "text/plain+int:2": "int_val",
      "text/plain+float:2.5": "float_val",
      "text/plain+bool:True": "bool_val",
      "text/plain+none:": "none_val",
      "text/plain+tuple:[1, 2]": "tuple_val",
      "text/plain+frozenset:[3, 4]": "fs_val",
      "text/plain+str:text/plain+int:2": "escaped_str_val",
      plain: "unchanged",
    };

    const { container } = render(<JsonOutput data={data} format="tree" />);
    const text = container.textContent ?? "";

    // `text/plain+str:` is the escape prefix — must never survive in output.
    expect(text).not.toContain("text/plain+str:");
    // Other encoded prefixes must not leak as-is. (They can still appear
    // inside the unescaped original string key `"text/plain+int:2"`,
    // which is intentional — but not for types *other* than int.)
    expect(text).not.toContain("text/plain+bool:True");
    expect(text).not.toContain("text/plain+tuple:[");
    expect(text).not.toContain("text/plain+frozenset:[");
    expect(text).not.toContain("text/plain+none:");

    // Decoded visual forms are present with Python-style affordances.
    expect(text).toContain('None:"none_val"');
    expect(text).toContain('True:"bool_val"');
    expect(text).toContain('2:"int_val"');
    expect(text).toContain('2.5:"float_val"');
    expect(text).toContain('(1, 2):"tuple_val"');
    expect(text).toContain('frozenset({3, 4}):"fs_val"');
    // Escaped str key renders as the original literal string (quoted).
    expect(text).toContain('"text/plain+int:2":"escaped_str_val"');
    // Plain string key unchanged.
    expect(text).toContain('"plain":"unchanged"');
  });

  it("renders 1-tuple and empty-frozenset keys with correct Python syntax", () => {
    // Regressions caught in review: `(1)` is not a tuple (needs `(1,)`),
    // and `frozenset({})` reads like constructing from an empty dict
    // (should be `frozenset()`). Locks in the tree-view rendering so these
    // don't slip back.
    const data = {
      "text/plain+tuple:[42]": "one_tuple",
      "text/plain+tuple:[]": "empty_tuple",
      "text/plain+frozenset:[]": "empty_fs",
      "text/plain+frozenset:[1]": "one_fs",
    };

    const { container } = render(<JsonOutput data={data} format="tree" />);
    const text = container.textContent ?? "";

    expect(text).toContain('(42,):"one_tuple"'); // trailing comma
    expect(text).toContain('():"empty_tuple"');
    expect(text).toContain('frozenset():"empty_fs"'); // not `frozenset({})`
    expect(text).toContain('frozenset({1}):"one_fs"');
  });

  it("quotes integer-like string keys to distinguish them from int keys", () => {
    // Without this, `"2"` and the decoded int `2` look identical — the
    // textea viewer drops quotes from integer-like string keys by default.
    const data = {
      "2": "string_two",
      "text/plain+int:2": "int_two",
    };

    const { container } = render(<JsonOutput data={data} format="tree" />);
    const text = container.textContent ?? "";

    expect(text).toContain('"2":"string_two"'); // quoted
    expect(text).toContain('2:"int_two"'); // unquoted
    // Non-integer string keys still render without our intervention.
    expect(text).not.toContain("text/plain+"); // prefix stripped from int key
  });
});
