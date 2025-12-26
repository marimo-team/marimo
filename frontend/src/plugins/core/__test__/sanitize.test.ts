/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { sanitizeHtml } from "../sanitize";

describe("sanitizeHtml", () => {
  test("renders basic HTML", () => {
    const html = "<h1>Hello World</h1>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<h1>Hello World</h1>"`);
  });

  test("renders nested HTML", () => {
    const html = "<div><p>Paragraph</p><span>Span</span></div>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div><p>Paragraph</p><span>Span</span></div>"`,
    );
  });

  test("removes script tags", () => {
    const html = "<div>Hello</div><script>alert('XSS')</script>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<div>Hello</div>"`);
  });

  test("removes inline script in onclick", () => {
    const html = "<button onclick=\"alert('XSS')\">Click me</button>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<button>Click me</button>"`,
    );
  });

  test("removes javascript: protocol in href", () => {
    const html = "<a href=\"javascript:alert('XSS')\">Link</a>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a target="_self">Link</a>"`,
    );
  });

  test("removes onerror attribute", () => {
    const html = '<img src="x" onerror="alert(\'XSS\')" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<img src="x">"`);
  });

  test("keeps form tags but removes action attribute", () => {
    const html = '<form action="/submit"><input type="text"/></form>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<form action="/submit"><input type="text"></form>"`,
    );
  });

  test("removes iframe tags", () => {
    const html = '<iframe src="https://evil.com"></iframe>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`""`);
  });

  test("removes embed tags", () => {
    const html = '<embed src="https://evil.com" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`""`);
  });

  test("removes object tags", () => {
    const html = '<object data="https://evil.com"></object>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`""`);
  });

  test("preserves safe anchor with target=_blank", () => {
    const html = '<a href="https://example.com" target="_blank">Link</a>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a href="https://example.com" target="_blank" rel="noopener noreferrer">Link</a>"`,
    );
  });

  test("adds target=_self to anchor without target", () => {
    const html = '<a href="https://example.com">Link</a>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a href="https://example.com" target="_self">Link</a>"`,
    );
  });

  test("preserves target=_self on anchor", () => {
    const html = '<a href="https://example.com" target="_self">Link</a>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a href="https://example.com" target="_self">Link</a>"`,
    );
  });

  test("preserves target=_parent on anchor", () => {
    const html = '<a href="https://example.com" target="_parent">Link</a>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a href="https://example.com" target="_parent">Link</a>"`,
    );
  });

  test("preserves SVG elements", () => {
    const html =
      '<svg width="100" height="100"><circle cx="50" cy="50" r="40" /></svg>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<svg width="100" height="100"><circle cx="50" cy="50" r="40"></circle></svg>"`,
    );
  });

  test("removes script from SVG", () => {
    const html = '<svg><script>alert("XSS")</script><circle r="10" /></svg>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<svg><circle r="10"></circle></svg>"`,
    );
  });

  test("preserves MathML", () => {
    const html = "<math><mi>x</mi><mo>=</mo><mn>2</mn></math>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<math><mi>x</mi><mo>=</mo><mn>2</mn></math>"`,
    );
  });

  test("preserves custom marimo elements", () => {
    const html = '<marimo-slider value="50"></marimo-slider>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<marimo-slider value="50"></marimo-slider>"`,
    );
  });

  test("preserves marimo elements with valid naming", () => {
    const html = "<marimo-custom-element></marimo-custom-element>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<marimo-custom-element></marimo-custom-element>"`,
    );
  });

  test("removes invalid custom elements (not marimo-*)", () => {
    const html = "<custom-element>Content</custom-element>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"Content"`);
  });

  test("preserves marimo elements with simple data attribute", () => {
    const html = '<marimo-test data-value="simple">Test</marimo-test>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<marimo-test data-value="simple">Test</marimo-test>"`,
    );
  });

  test("preserves marimo-mermaid with data-diagram attribute", () => {
    const html =
      "<marimo-mermaid data-diagram='&quot;sequenceDiagram&#92;n    Alice-&gt;&gt;John&#92;n    John--&gt;&gt;Alice&#92;n    &quot;'></marimo-mermaid>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<marimo-mermaid data-diagram="&quot;sequenceDiagram\\n    Alice->>John\\n    John-->>Alice\\n    &quot;"></marimo-mermaid>"`,
    );
  });

  test("keeps style tags with FORCE_BODY", () => {
    const html = "<style>body { color: red; }</style><p>Text</p>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<style>body { color: red; }</style><p>Text</p>"`,
    );
  });

  test("removes link tags", () => {
    const html = '<link rel="stylesheet" href="evil.css" /><p>Text</p>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<p>Text</p>"`);
  });

  test("removes meta tags", () => {
    const html = '<meta http-equiv="refresh" content="0;url=evil.com" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`""`);
  });

  test("removes base tags", () => {
    const html = '<base href="https://evil.com" /><p>Text</p>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<p>Text</p>"`);
  });

  test("preserves safe HTML entities", () => {
    const html = "<p>&lt;div&gt; &amp; &quot;quotes&quot;</p>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<p>&lt;div&gt; &amp; "quotes"</p>"`,
    );
  });

  test("preserves data attributes", () => {
    const html = '<div data-id="123" data-name="test">Content</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div data-id="123" data-name="test">Content</div>"`,
    );
  });

  test("preserves aria attributes", () => {
    const html = '<button aria-label="Close" aria-hidden="true">X</button>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<button aria-label="Close" aria-hidden="true">X</button>"`,
    );
  });

  test("preserves class and id attributes", () => {
    const html = '<div id="main" class="container primary">Content</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div id="main" class="container primary">Content</div>"`,
    );
  });

  test("removes dangerous event handlers", () => {
    const html =
      '<div onload="alert(1)" onmouseover="alert(2)" onfocus="alert(3)">Text</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<div>Text</div>"`);
  });

  test("handles empty string", () => {
    const html = "";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`""`);
  });

  test("handles text without tags", () => {
    const html = "Just plain text";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"Just plain text"`);
  });

  test("handles malformed HTML", () => {
    const html = "<div><p>Unclosed div";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div><p>Unclosed div</p></div>"`,
    );
  });

  test("removes data URIs with javascript", () => {
    const html = '<a href="data:text/html,<script>alert(1)</script>">Link</a>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a target="_self">Link</a>"`,
    );
  });

  test("preserves safe data URIs", () => {
    const html = '<img src="data:image/png;base64,iVBORw0KGgo=" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<img src="data:image/png;base64,iVBORw0KGgo=">"`,
    );
  });

  test("removes srcdoc attribute from iframe", () => {
    const html = '<iframe srcdoc="<script>alert(1)</script>"></iframe>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`""`);
  });

  test("handles complex nested structure", () => {
    const html = `
      <div class="container">
        <header>
          <h1>Title</h1>
          <nav><a href="/home">Home</a></nav>
        </header>
        <main>
          <article>
            <p>Content</p>
          </article>
        </main>
      </div>
    `;
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`
      "
            <div class="container">
              <header>
                <h1>Title</h1>
                <nav><a href="/home" target="_self">Home</a></nav>
              </header>
              <main>
                <article>
                  <p>Content</p>
                </article>
              </main>
            </div>
          "
    `);
  });

  test("keeps marquee and blink tags (not considered dangerous by DOMPurify)", () => {
    const html = "<marquee>Scrolling text</marquee><blink>Blinking</blink>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<marquee>Scrolling text</marquee><blink>Blinking</blink>"`,
    );
  });

  test("preserves table structures", () => {
    const html = "<table><tr><td>Cell 1</td><td>Cell 2</td></tr></table>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<table><tbody><tr><td>Cell 1</td><td>Cell 2</td></tr></tbody></table>"`,
    );
  });

  test("removes xml-stylesheet processing instructions", () => {
    const html =
      '<?xml-stylesheet href="evil.xsl" type="text/xsl"?><div>Text</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<div>Text</div>"`);
  });

  test("removes use element from SVG", () => {
    const html = '<svg><use xlink:href="#icon"></use></svg>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<svg></svg>"`);
  });

  test("removes javascript in SVG href", () => {
    const html =
      '<svg><a href="javascript:alert(1)"><text>Click</text></a></svg>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<svg><a><text>Click</text></a></svg>"`,
    );
  });

  test("preserves img with valid src", () => {
    const html = '<img src="https://example.com/image.png" alt="Image" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<img src="https://example.com/image.png" alt="Image">"`,
    );
  });

  test("handles multiple scripts interleaved", () => {
    const html =
      "<div>Text1</div><script>evil1()</script><p>Text2</p><script>evil2()</script>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div>Text1</div><p>Text2</p>"`,
    );
  });

  test("removes frameset and frame tags", () => {
    const html = '<frameset><frame src="page.html" /></frameset>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`""`);
  });

  test("handles vbscript: protocol", () => {
    const html = '<a href="vbscript:msgbox()">Link</a>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a target="_self">Link</a>"`,
    );
  });

  test("removes autofocus and onfocus from input", () => {
    const html = '<input type="hidden" autofocus onfocus="alert(1)" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<input type="hidden">"`);
  });

  test("removes formaction attribute", () => {
    const html = '<button formaction="javascript:alert(1)">Click</button>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<button>Click</button>"`,
    );
  });

  test("handles nested script-like content", () => {
    const html = "<div>&lt;script&gt;alert(1)&lt;/script&gt;</div>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div>&lt;script&gt;alert(1)&lt;/script&gt;</div>"`,
    );
  });

  test("preserves valid inline styles", () => {
    const html = '<div style="color: blue; font-size: 14px;">Styled</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div style="color: blue; font-size: 14px;">Styled</div>"`,
    );
  });

  test("keeps expression() in styles (legacy IE only)", () => {
    const html = '<div style="width: expression(alert(1));">Text</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div style="width: expression(alert(1));">Text</div>"`,
    );
  });

  test("keeps moz-binding in styles (legacy Firefox only)", () => {
    const html = '<div style="-moz-binding: url(xss.xml#xss)">Text</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div style="-moz-binding: url(xss.xml#xss)">Text</div>"`,
    );
  });

  test("preserves title and alt attributes", () => {
    const html = '<img src="pic.jpg" alt="Picture" title="A nice picture" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<img src="pic.jpg" alt="Picture" title="A nice picture">"`,
    );
  });

  test("handles multiple targets on links", () => {
    const html = '<a href="/" target="_top">Link</a>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<a href="/" target="_top">Link</a>"`,
    );
  });

  test("removes on* attributes comprehensively", () => {
    const html =
      '<div onabort="alert(1)" onblur="alert(2)" onchange="alert(3)" ondblclick="alert(4)">Text</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<div>Text</div>"`);
  });

  test("removes SVG foreignObject", () => {
    const html =
      "<svg><foreignObject><body><p>Text</p></body></foreignObject></svg>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<svg></svg>"`);
  });

  test("removes xlink:href with javascript in SVG", () => {
    const html = '<svg><a xlink:href="javascript:alert(1)">Click</a></svg>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<svg><a>Click</a></svg>"`,
    );
  });

  test("preserves role attributes", () => {
    const html = '<div role="button" tabindex="0">Clickable</div>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div role="button" tabindex="0">Clickable</div>"`,
    );
  });

  test("handles HTML comments", () => {
    const html = "<!-- Comment --><p>Text</p>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<p>Text</p>"`);
  });

  test("removes conditional comments", () => {
    const html = "<!--[if IE]><script>alert(1)</script><![endif]--><p>Text</p>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"<p>Text</p>"`);
  });

  test("preserves pre and code elements", () => {
    const html = "<pre><code>const x = 1;</code></pre>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<pre><code>const x = 1;</code></pre>"`,
    );
  });

  test("handles mixed content with scripts", () => {
    const html =
      "<div><p>Safe</p><script>evil()</script><p>More safe</p></div>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<div><p>Safe</p><p>More safe</p></div>"`,
    );
  });

  test("preserves video and audio elements", () => {
    const html = '<video src="video.mp4" controls></video>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<video src="video.mp4" controls=""></video>"`,
    );
  });

  test("handles source elements in video", () => {
    const html =
      '<video controls><source src="video.mp4" type="video/mp4" /></video>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<video controls=""><source src="video.mp4" type="video/mp4"></video>"`,
    );
  });

  test("removes import statement in style", () => {
    const html = '<style>@import url("evil.css");</style>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<style>@import url("evil.css");</style>"`,
    );
  });

  test("handles HTML5 semantic elements", () => {
    const html =
      "<article><section><header>Title</header><footer>Footer</footer></section></article>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<article><section><header>Title</header><footer>Footer</footer></section></article>"`,
    );
  });

  test("preserves canvas element", () => {
    const html = '<canvas id="myCanvas" width="200" height="100"></canvas>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<canvas id="myCanvas" width="200" height="100"></canvas>"`,
    );
  });

  test("handles details and summary elements", () => {
    const html =
      "<details><summary>Click me</summary><p>Hidden content</p></details>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<details><summary>Click me</summary><p>Hidden content</p></details>"`,
    );
  });

  test("preserves iconify-icon custom element", () => {
    const html = '<iconify-icon icon="lucide:leaf"></iconify-icon>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<iconify-icon icon="lucide:leaf"></iconify-icon>"`,
    );
  });

  test("preserves iconify-icon with all attributes", () => {
    const html =
      '<iconify-icon icon="lucide:rocket" width="24px" height="24px" inline="" flip="horizontal" rotate="90deg" style="color: blue;"></iconify-icon>';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<iconify-icon icon="lucide:rocket" width="24px" height="24px" inline="" flip="horizontal" rotate="90deg" style="color: blue;"></iconify-icon>"`,
    );
  });

  test("preserves self-closing iconify-icon", () => {
    const html = '<iconify-icon icon="lucide:star" />';
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(
      `"<iconify-icon icon="lucide:star"></iconify-icon>"`,
    );
  });

  test("still removes other non-marimo/non-iconify custom elements", () => {
    const html = "<some-custom-element>Content</some-custom-element>";
    expect(sanitizeHtml(html)).toMatchInlineSnapshot(`"Content"`);
  });
});
