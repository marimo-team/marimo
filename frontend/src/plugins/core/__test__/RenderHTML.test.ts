/* Copyright 2026 Marimo. All rights reserved. */
import type { ExtractAtomValue } from "jotai";
import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
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

  test("img has key derived from src so React remounts on src change", () => {
    const html = '<img src="https://cdn.example.com/a.png" alt="a">';
    const result = parseHtml({ html }) as React.ReactElement;
    expect(result.key).toBe("https://cdn.example.com/a.png-0");
  });

  test("multiple imgs each get distinct keys", () => {
    const html =
      '<div><img src="https://cdn.example.com/a.png"><img src="https://cdn.example.com/b.png"></div>';
    const result = parseHtml({ html }) as React.ReactElement<{
      children: React.ReactElement[];
    }>;
    const children = result.props.children;
    expect(children[0].key).toBe("https://cdn.example.com/a.png-0");
    expect(children[1].key).toBe("https://cdn.example.com/b.png-1");
  });

  test("img without src is left alone", () => {
    const html = "<img>";
    const result = parseHtml({ html }) as React.ReactElement;
    expect(result.key).toBeNull();
  });

  test("img with data: URI is not keyed (inline, no network fetch)", () => {
    const longPayload = "A".repeat(10_000);
    const html = `<img src="data:image/png;base64,${longPayload}">`;
    const result = parseHtml({ html }) as React.ReactElement;
    // No remount-on-src needed for inline images, so we leave the key
    // unset rather than bloat it with the base64 payload.
    expect(result.key).toBeNull();
  });

  test("img with uppercase DATA: URI is also skipped (scheme is case-insensitive)", () => {
    const html = `<img src="DATA:image/png;base64,${"A".repeat(100)}">`;
    const result = parseHtml({ html }) as React.ReactElement;
    expect(result.key).toBeNull();
  });

  test("img wrapped by data-tooltip is still keyed by src", () => {
    const html =
      '<img src="https://cdn.example.com/a.png" data-tooltip="hi" alt="a">';
    const result = parseHtml({ html }) as React.ReactElement;
    // Outer Tooltip carries the src-based key so it remounts on src change,
    // forcing the inner <img> to remount as well.
    expect(result.key).toBe("https://cdn.example.com/a.png-0");
  });

  test("img wrapped by data-marimo-doc is still keyed by src", () => {
    const html =
      '<img src="https://cdn.example.com/b.png" data-marimo-doc="foo.bar">';
    const result = parseHtml({ html }) as React.ReactElement;
    expect(result.key).toBe("https://cdn.example.com/b.png-0");
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

describe("replaceSrcScripts trust gate", () => {
  let previousHasRunAnyCell: ExtractAtomValue<typeof hasRunAnyCellAtom>;
  let previousConfig: ExtractAtomValue<typeof userConfigAtom>;
  let previousMode: ExtractAtomValue<typeof initialModeAtom>;
  const windowWithExport = window as Window & {
    __MARIMO_EXPORT_CONTEXT__?: unknown;
  };

  function clearTrustSignals() {
    const cleared = parseUserConfig({});
    store.set(hasRunAnyCellAtom, false);
    store.set(userConfigAtom, {
      ...cleared,
      runtime: { ...cleared.runtime, auto_instantiate: false },
    });
    store.set(initialModeAtom, "edit");
    delete windowWithExport.__MARIMO_EXPORT_CONTEXT__;
  }

  beforeEach(() => {
    previousHasRunAnyCell = store.get(hasRunAnyCellAtom);
    previousConfig = store.get(userConfigAtom);
    previousMode = store.get(initialModeAtom);
    clearTrustSignals();
    for (const s of document.head.querySelectorAll(
      'script[src^="https://cdn.example.com/"]',
    )) {
      s.remove();
    }
  });

  afterEach(() => {
    store.set(hasRunAnyCellAtom, previousHasRunAnyCell);
    store.set(userConfigAtom, previousConfig);
    store.set(initialModeAtom, previousMode);
    delete windowWithExport.__MARIMO_EXPORT_CONTEXT__;
    for (const s of document.head.querySelectorAll(
      'script[src^="https://cdn.example.com/"]',
    )) {
      s.remove();
    }
  });

  test("drops <script src> in untrusted edit mode", () => {
    parseHtml({
      html: '<script src="https://cdn.example.com/unrun.js"></script>',
    });
    expect(
      document.head.querySelector(
        'script[src="https://cdn.example.com/unrun.js"]',
      ),
    ).toBeNull();
  });

  test("loads <script src> once a cell has been run", () => {
    store.set(hasRunAnyCellAtom, true);
    parseHtml({
      html: '<script src="https://cdn.example.com/ok.js"></script>',
    });
    expect(
      document.head.querySelector(
        'script[src="https://cdn.example.com/ok.js"]',
      ),
    ).not.toBeNull();
  });

  test("loads <script src> when a trusted export context is installed", () => {
    windowWithExport.__MARIMO_EXPORT_CONTEXT__ = { trusted: true };
    parseHtml({
      html: '<script src="https://cdn.example.com/export.js"></script>',
    });
    expect(
      document.head.querySelector(
        'script[src="https://cdn.example.com/export.js"]',
      ),
    ).not.toBeNull();
  });
});

describe("wrapTooltipTargets", () => {
  test("data-tooltip wraps element in Tooltip component", () => {
    const html = '<span data-tooltip="Hello world">Hover me</span>';
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <Tooltip
        content="Hello world"
      >
        <span
          data-tooltip="Hello world"
        >
          Hover me
        </span>
      </Tooltip>
    `);
  });

  test("element without data-tooltip is not wrapped", () => {
    const html = "<span>No tooltip</span>";
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <span>
        No tooltip
      </span>
    `);
  });

  test("data-tooltip on nested element wraps only that element", () => {
    const html = '<p>Outer <span data-tooltip="tip">inner</span> text</p>';
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <p>
        Outer 
        <Tooltip
          content="tip"
        >
          <span
            data-tooltip="tip"
          >
            inner
          </span>
        </Tooltip>
         text
      </p>
    `);
  });

  test("data-tooltip on marimo custom elements is not wrapped", () => {
    const html =
      '<marimo-button data-tooltip="&quot;Run clicky&quot;">click</marimo-button>';
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <marimo-button
        data-tooltip=""Run clicky""
      >
        click
      </marimo-button>
    `);
  });

  test("data-tooltip on non-marimo custom elements is still wrapped", () => {
    const html = '<my-widget data-tooltip="info">content</my-widget>';
    expect(parseHtml({ html })).toMatchInlineSnapshot(`
      <Tooltip
        content="info"
      >
        <my-widget
          data-tooltip="info"
        >
          content
        </my-widget>
      </Tooltip>
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
