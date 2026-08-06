/* Copyright 2026 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ReadonlyCode } from "../readonly-python-code";

const themeState = vi.hoisted(() => ({
  value: "light" as "light" | "dark",
}));

vi.mock("@/theme/useTheme", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/theme/useTheme")>();
  return {
    ...actual,
    useTheme: () => ({ theme: themeState.value }),
  };
});

beforeAll(() => {
  SetupMocks.resizeObserver();
  Object.defineProperty(Range.prototype, "getClientRects", {
    configurable: true,
    value: () => [],
  });
});

beforeEach(() => {
  themeState.value = "light";
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

function getEditorIdentity(view: EditorView) {
  return {
    doc: view.state.doc,
    dom: view.dom,
    contentDOM: view.contentDOM,
    scrollDOM: view.scrollDOM,
  };
}

function expectEditorIdentity(
  view: EditorView,
  identity: ReturnType<typeof getEditorIdentity>,
) {
  expect(view.state.doc).toBe(identity.doc);
  expect(view.dom).toBe(identity.dom);
  expect(view.contentDOM).toBe(identity.contentDOM);
  expect(view.scrollDOM).toBe(identity.scrollDOM);
}

describe("ReadonlyCode", () => {
  it("reconfigures the theme without replacing the editor", async () => {
    let createdView: EditorView | undefined;
    const onCreateEditor = (view: EditorView) => {
      createdView = view;
    };
    const renderCode = (id: string) => (
      <TooltipProvider>
        <ReadonlyCode
          id={id}
          code={"line_1 = 1\nline_2 = 2\nline_3 = 3"}
          showCopyCode={false}
          onCreateEditor={onCreateEditor}
        />
      </TooltipProvider>
    );

    const { rerender } = render(renderCode("light"));
    await waitFor(() => {
      expect(createdView).toBeDefined();
    });

    const view = createdView;
    if (!view) {
      throw new Error("ReadonlyCode did not create an editor view");
    }
    const identity = getEditorIdentity(view);
    expect(view.state.facet(EditorView.darkTheme)).toBe(false);

    themeState.value = "dark";
    rerender(renderCode("dark"));
    await waitFor(() => {
      expect(view.state.facet(EditorView.darkTheme)).toBe(true);
    });
    expect(createdView).toBe(view);
    expectEditorIdentity(view, identity);

    themeState.value = "light";
    rerender(renderCode("light-again"));
    await waitFor(() => {
      expect(view.state.facet(EditorView.darkTheme)).toBe(false);
    });
    expect(createdView).toBe(view);
    expectEditorIdentity(view, identity);
  });

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
