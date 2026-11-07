/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { copyToClipboard } from "@/utils/copy";
import { renderHTML } from "../RenderHTML";

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../sanitize", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../sanitize")>()),
  useSanitizeHtml: () => true,
}));

test.each([
  {
    name: "syntax highlighting and whitespace",
    html: '<div class="codehilite"><pre><span></span><code><span class="k">if</span> x &lt; 2:\n    print(&quot;hello&quot;)\n\n</code></pre></div>',
    expected: 'if x < 2:\n    print("hello")\n\n',
  },
  {
    name: "a block title",
    html: '<div class="codehilite"><span class="filename">example.py</span><pre><span></span><code>print("hello")\n</code></pre></div>',
    expected: 'print("hello")\n',
  },
  {
    name: "line numbers in a separate column",
    html: '<div class="codehilite"><table class="codehilitetable"><tbody><tr><td class="linenos"><div class="linenodiv"><pre><span></span><span class="normal">1</span>\n<span class="normal">2</span></pre></div></td><td class="code"><div><pre><span></span><code>print("hello")\nprint("world")\n</code></pre></div></td></tr></tbody></table></div>',
    expected: 'print("hello")\nprint("world")\n',
  },
  {
    name: "hidden fences outside the code",
    html: '<div class="codehilite"><span hidden>~~~python\n</span><pre><code>print("hello")\n</code></pre><span hidden>~~~</span></div>',
    expected: 'print("hello")\n',
  },
  {
    name: "literal fences inside the code",
    html: '<div class="codehilite"><pre><code>~~~python\nprint("``` and ~~~")\n~~~\n</code></pre></div>',
    expected: '~~~python\nprint("``` and ~~~")\n~~~\n',
  },
  {
    name: "an empty code element",
    html: '<div class="codehilite"><span class="filename">empty.py</span><pre><code></code></pre></div>',
    expected: "",
  },
  {
    name: "highlighted HTML without a code element",
    html: '<div class="codehilite"><pre><span class="nb">print</span>("hello")\n</pre></div>',
    expected: 'print("hello")\n',
  },
])("copies code from $name", async ({ html, expected }) => {
  const { getByRole } = render(renderHTML({ html }));

  fireEvent.click(getByRole("button", { name: "Copy to clipboard" }));

  await waitFor(() => {
    expect(copyToClipboard).toHaveBeenCalledExactlyOnceWith(expected);
  });
});
