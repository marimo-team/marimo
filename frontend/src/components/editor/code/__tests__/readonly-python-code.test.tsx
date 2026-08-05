/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ReadonlyCode } from "../readonly-python-code";

beforeAll(() => {
  SetupMocks.resizeObserver();
});

/**
 * The only button is the show/hide toggle: copy is disabled and the
 * insert-cell button is off by default.
 */
function renderReadonly(props: { initiallyHideCode?: boolean }) {
  return render(
    <TooltipProvider>
      <ReadonlyCode code="x = 1" showCopyCode={false} {...props} />
    </TooltipProvider>,
  );
}

function isCollapsed(root: ParentNode) {
  return root.querySelector(".cm")?.classList.contains("opacity-20") ?? false;
}

describe("ReadonlyCode", () => {
  it("starts collapsed when initiallyHideCode is true", () => {
    const { container } = renderReadonly({ initiallyHideCode: true });
    expect(isCollapsed(container)).toBe(true);
  });

  it("starts expanded when initiallyHideCode is false", () => {
    const { container } = renderReadonly({ initiallyHideCode: false });
    expect(isCollapsed(container)).toBe(false);
  });

  it("starts expanded when initiallyHideCode is unset", () => {
    const { container } = renderReadonly({});
    expect(isCollapsed(container)).toBe(false);
  });

  it("toggles visibility locally on click", () => {
    const { container } = renderReadonly({ initiallyHideCode: true });
    const toggle = screen.getByRole("button");

    fireEvent.click(toggle);
    expect(isCollapsed(container)).toBe(false);

    fireEvent.click(toggle);
    expect(isCollapsed(container)).toBe(true);
  });

  it("keeps each instance's visibility independent", () => {
    const { container } = render(
      <TooltipProvider>
        <ReadonlyCode
          code="a = 1"
          showCopyCode={false}
          initiallyHideCode={true}
        />
        <ReadonlyCode
          code="b = 2"
          showCopyCode={false}
          initiallyHideCode={true}
        />
      </TooltipProvider>,
    );
    const [firstToggle] = screen.getAllByRole("button");
    const [first, second] = container.querySelectorAll(".cm");

    fireEvent.click(firstToggle);

    expect(first.classList.contains("opacity-20")).toBe(false);
    expect(second.classList.contains("opacity-20")).toBe(true);
  });
});
