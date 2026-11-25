/* Copyright 2026 Marimo. All rights reserved. */
import { render, cleanup } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { CodePlaceholder } from "../code-placeholder";

afterEach(cleanup);

it("keeps every line searchable, highlighted, and escaped without an editor", () => {
  const code = Array.from({ length: 100 }, (_, i) => `x${i} = "<script>"`).join(
    "\n",
  );
  const { container } = render(<CodePlaceholder code={code} />);
  expect(container.textContent).toBe(code);
  expect(container.querySelector(".tok-string")).not.toBeNull();
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector(".cm-editor")).toBeNull();
});

it("shows markdown editor text instead of its Python wrapper", () => {
  const { container } = render(
    <CodePlaceholder code={'mo.md(r"""hello""")'} />,
  );
  expect(container.textContent).toBe("hello");
});
