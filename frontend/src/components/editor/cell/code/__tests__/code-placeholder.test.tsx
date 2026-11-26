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

it("renders a bounded number of lines and keeps the rest of a long cell as height", () => {
  const code = Array.from({ length: 5000 }, (_, i) => `x${i} = ${i}`).join(
    "\n",
  );
  const { container } = render(<CodePlaceholder code={code} />);
  const placeholder = container.querySelector<HTMLElement>(
    ".mo-code-placeholder",
  );

  expect(container.textContent?.split("\n")).toHaveLength(200);
  expect(container.textContent?.startsWith("x0 = 0\n")).toBe(true);
  expect(placeholder?.style.getPropertyValue("--mo-hidden-lines")).toBe("4800");
  expect(placeholder?.style.getPropertyValue("--mo-gutter-digits")).toBe("4");
  expect(container.querySelector(".mo-code-placeholder-rest")).not.toBeNull();
});
