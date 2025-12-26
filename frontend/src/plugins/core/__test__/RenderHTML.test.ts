/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { visibleForTesting } from "../RenderHTML";

const { parseHtml } = visibleForTesting;

describe("parseHtml", () => {
  test("renders HTML", () => {
    const html = "<h1>Hello</h1>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <h1>
        Hello
      </h1>
    `);
  });

  test("no closing HTML", () => {
    const html = "<h1>Hello";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <h1>
        Hello
      </h1>
    `);
  });

  test("script", () => {
    const html = "<h1>Hello</h1><script>alert('hi')</script>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
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
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <div
        dangerouslySetInnerHTML={
          {
            "__html": "<iframe src="https://example.com" crossorigin=""></iframe>",
          }
        }
      />
    `);
  });

  test("codehilite with copy button", () => {
    const html =
      '<div class="codehilite"><pre><code>console.log("Hello");</code></pre></div>';
    const result = parseHtml({ html });

    // Check that the result is wrapped in a CopyableCode component
    expect(result).toMatchInlineSnapshot(`
      <CopyableCode>
        <div
          className="codehilite"
        >
          <pre>
            <code>
              console.log("Hello");
            </code>
          </pre>
        </div>
      </CopyableCode>
    `);
  });

  test("custom tags - valid", () => {
    let html = "<foobar></foobar>";
    expect(parseHtml({ html })).toMatchInlineSnapshot("<foobar />");

    html = "<foobar2></foobar2>";
    expect(parseHtml({ html })).toMatchInlineSnapshot("<foobar2 />");

    html = "<marimo-slider></marimo-slider>";
    expect(parseHtml({ html })).toMatchInlineSnapshot("<marimo-slider />");
  });

  test("custom tags - invalid", () => {
    let html = "<c&></c&> lorem";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      [
        <React.Fragment />,
        " lorem",
      ]
    `);

    html = "<p><someone@gmail.com></p>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <p>
        <React.Fragment />
      </p>
    `);

    html = "<p><1></p>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <p>
        &lt;1&gt;
      </p>
    `);

    html = "<p><1/></p>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <p>
        &lt;1/&gt;
      </p>
    `);

    html = "<p><a:b></a:b></p>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <p>
        <React.Fragment />
      </p>
    `);
  });

  test("removes body tags but preserves children", () => {
    const html = "<body><h1>Hello</h1><p>World</p></body>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <React.Fragment>
        <h1>
          Hello
        </h1>
        <p>
          World
        </p>
      </React.Fragment>
    `);
  });

  test("removes nested body tags", () => {
    const html = "<div><body><span>Content</span></body></div>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <div>
        <React.Fragment>
          <span>
            Content
          </span>
        </React.Fragment>
      </div>
    `);
  });

  test("removes html tags but preserves children", () => {
    const html =
      "<html><head><title>Test</title></head><body><p>Content</p></body></html>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <React.Fragment>
        <head>
          <title>
            Test
          </title>
        </head>
        <React.Fragment>
          <p>
            Content
          </p>
        </React.Fragment>
      </React.Fragment>
    `);
  });

  test("removes nested html tags", () => {
    const html = "<div><html><span>Content</span></html></div>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <div>
        <React.Fragment>
          <span>
            Content
          </span>
        </React.Fragment>
      </div>
    `);
  });

  test("remove nested body in html", () => {
    const html = "<html><body><span>Content</span></body></html>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <React.Fragment>
        <React.Fragment>
          <span>
            Content
          </span>
        </React.Fragment>
      </React.Fragment>
    `);
  });
});

describe("parseHtml with < nad >", () => {
  const html =
    'thread <unnamed> panicked at "assertion failed: `(left == right)`"';
  test("<unnamed>", () => {
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      [
        "thread ",
        <unnamed>
           panicked at "assertion failed: \`(left == right)\`"
        </unnamed>,
      ]
    `);
  });

  test("<unnamed> sanitized", () => {
    const sanitized = html.replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    expect(parseHtml({ html: sanitized })).toMatchInlineSnapshot(
      `"thread <unnamed> panicked at "assertion failed: \`(left == right)\`""`,
    );
  });
});
