/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JsonOutput } from "../JsonOutput";

describe("JsonOutput MIME rendering", () => {
  it("renders text, rich content, and Python collections", () => {
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

    expect(container.textContent).toContain('"text":Hello');
    expect(container.querySelector("strong")).toHaveTextContent("Bold");
    expect(container.querySelector("img")).toHaveAttribute(
      "src",
      "data:image/png;base64,xyz...",
    );
    expect(container.textContent).toContain('"set":{1, 2, 3}');
    expect(container.textContent).toContain('"tuple":(10, 20)');
    expect(container.textContent).toContain("application/custom:data");
    expect(container.textContent).toContain('"boolean":True');
  });

  it("keeps MIME strings literal in JSON mode", () => {
    const { container } = render(
      <JsonOutput
        data={{ value: "text/plain+tuple:[42]" }}
        valueTypes="json"
      />,
    );
    expect(container.textContent).toContain('"value":"text/plain+tuple:[42]"');
  });

  it("renders singleton tuples and escaped collection strings", () => {
    const { container } = render(
      <JsonOutput
        data={{
          tuple: "text/plain+tuple:[42]",
          set: 'text/plain+set:["text/plain:literal"]',
        }}
      />,
    );
    expect(container.textContent).toContain('"tuple":(42,)');
    expect(container.textContent).toContain('"set":{"text/plain:literal"}');
  });

  it("renders encoded non-string keys with Python-style affordances", () => {
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

    expect(text).not.toContain("text/plain+str:");
    expect(text).not.toContain("text/plain+bool:True");
    expect(text).not.toContain("text/plain+tuple:[");
    expect(text).not.toContain("text/plain+frozenset:[");
    expect(text).not.toContain("text/plain+none:");

    expect(text).toContain('None:"none_val"');
    expect(text).toContain('True:"bool_val"');
    expect(text).toContain('2:"int_val"');
    expect(text).toContain('2.5:"float_val"');
    expect(text).toContain('(1, 2):"tuple_val"');
    expect(text).toContain('frozenset({3, 4}):"fs_val"');
    expect(text).toContain('"text/plain+int:2":"escaped_str_val"');
    expect(text).toContain('"plain":"unchanged"');
  });

  it("renders 1-tuple and empty-frozenset keys with correct Python syntax", () => {
    const data = {
      "text/plain+tuple:[42]": "one_tuple",
      "text/plain+tuple:[]": "empty_tuple",
      "text/plain+frozenset:[]": "empty_fs",
      "text/plain+frozenset:[1]": "one_fs",
    };

    const { container } = render(<JsonOutput data={data} format="tree" />);
    const text = container.textContent ?? "";

    expect(text).toContain('(42,):"one_tuple"');
    expect(text).toContain('():"empty_tuple"');
    expect(text).toContain('frozenset():"empty_fs"');
    expect(text).toContain('frozenset({1}):"one_fs"');
  });

  it("quotes integer-like string keys to distinguish them from int keys", () => {
    const data = {
      "2": "string_two",
      "text/plain+int:2": "int_two",
    };

    const { container } = render(<JsonOutput data={data} format="tree" />);
    const text = container.textContent ?? "";

    expect(text).toContain('"2":"string_two"');
    expect(text).toContain('2:"int_two"');
    expect(text).not.toContain("text/plain+");
  });
});
