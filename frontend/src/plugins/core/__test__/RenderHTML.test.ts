/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { renderHTML } from "../RenderHTML";

describe("RenderHTML", () => {
  test("renders HTML", () => {
    const html = "<h1>Hello</h1>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      <h1>
        Hello
      </h1>
    `);
  });

  test("no closing HTML", () => {
    const html = "<h1>Hello";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      <h1>
        Hello
      </h1>
    `);
  });

  test("script", () => {
    const html = "<h1>Hello</h1><script>alert('hi')</script>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      [
        <h1>
          Hello
        </h1>,
        <script
          dangerouslySetInnerHTML={
            {
              "__html": "alert('hi')",
            }
          }
        />,
      ]
    `);
  });

  test("iframe", () => {
    const html = '<iframe src="https://example.com" "crossorigin"></iframe>';
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      <div
        dangerouslySetInnerHTML={
          {
            "__html": "<iframe src="https://example.com" crossorigin=""></iframe>",
          }
        }
      />
    `);
  });

  test("custom tags - valid", () => {
    let html = "<foobar></foobar>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`<foobar />`);

    html = "<foobar2></foobar2>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`<foobar2 />`);

    html = "<marimo-slider></marimo-slider>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`<marimo-slider />`);
  });

  test("custom tags - invalid", () => {
    let html = "<c&></c&> lorem";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      [
        <React.Fragment />,
        " lorem",
      ]
    `);

    html = "<p><someone@gmail.com></p>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      <p>
        <React.Fragment />
      </p>
    `);

    html = "<p><1></p>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      <p>
        &lt;1&gt;
      </p>
    `);

    html = "<p><1/></p>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      <p>
        &lt;1/&gt;
      </p>
    `);

    html = "<p><a:b></a:b></p>";
    expect(renderHTML({ html })).toMatchInlineSnapshot(`
      <p>
        <React.Fragment />
      </p>
    `);
  });
});
