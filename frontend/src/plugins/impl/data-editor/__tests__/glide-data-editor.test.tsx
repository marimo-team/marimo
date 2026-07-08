/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GlideDataEditor } from "../glide-data-editor";

const capturedPortalRef = vi.hoisted(() => ({
  ref: undefined as React.RefObject<HTMLElement> | undefined,
}));

vi.mock("@glideapps/glide-data-grid", async () => {
  const React = await import("react");
  return {
    default: React.forwardRef(function MockDataEditor(
      props: { portalElementRef?: React.RefObject<HTMLElement> },
      _ref: React.Ref<HTMLDivElement>,
    ) {
      capturedPortalRef.ref = props.portalElementRef;
      return <div data-testid="mock-data-editor" />;
    }),
    CompactSelection: {
      empty: () => ({}),
    },
    GridCellKind: {
      Text: "text",
      Number: "number",
      Boolean: "boolean",
    },
    GridColumnIcon: {
      ProtectedColumnOverlay: "protected",
    },
  };
});

vi.mock("@/theme/useTheme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

const editorProps = {
  data: [{ name: "alice" }],
  setData: vi.fn(),
  columnFields: new Map([["name", "string"]]) as Map<string, "string">,
  setColumnFields: vi.fn(),
  editableColumns: "all" as const,
  edits: [],
  onAddEdits: vi.fn(),
  onAddRows: vi.fn(),
  onDeleteRows: vi.fn(),
  onRenameColumn: vi.fn(),
  onDeleteColumn: vi.fn(),
  onAddColumn: vi.fn(),
};

describe("GlideDataEditor portal", () => {
  let fullscreenElement: Element | null;

  beforeEach(() => {
    fullscreenElement = null;
    Object.defineProperty(document, "fullscreenElement", {
      get: () => fullscreenElement,
      configurable: true,
    });
    document.body
      .querySelectorAll("[data-testid='glide-data-editor-portal']")
      .forEach((node) => {
        node.remove();
      });
  });

  it("renders a body-level portal and passes it to DataEditor", async () => {
    const { container } = render(
      <TooltipProvider>
        <GlideDataEditor {...editorProps} />
      </TooltipProvider>,
    );

    const portal = screen.getByTestId("glide-data-editor-portal");
    expect(portal.parentElement).toBe(document.body);
    expect(container.contains(portal)).toBe(false);
    expect(capturedPortalRef.ref).toBeDefined();
    await waitFor(() => {
      expect(capturedPortalRef.ref?.current).toBe(portal);
    });
  });

  it("mounts into the fullscreen element when fullscreen is already active", () => {
    const fullscreenContainer = document.createElement("div");
    document.body.appendChild(fullscreenContainer);
    fullscreenElement = fullscreenContainer;

    render(
      <TooltipProvider>
        <GlideDataEditor {...editorProps} />
      </TooltipProvider>,
    );

    const portal = fullscreenContainer.querySelector(
      "[data-testid='glide-data-editor-portal']",
    );
    expect(portal).not.toBeNull();
    expect(portal?.parentElement).toBe(fullscreenContainer);

    fullscreenContainer.remove();
  });

  it("moves the portal into the fullscreen element while fullscreen is active", async () => {
    render(
      <TooltipProvider>
        <GlideDataEditor {...editorProps} />
      </TooltipProvider>,
    );

    expect(
      document.body.querySelector("[data-testid='glide-data-editor-portal']"),
    ).not.toBeNull();

    const fullscreenContainer = document.createElement("div");
    document.body.appendChild(fullscreenContainer);

    act(() => {
      fullscreenElement = fullscreenContainer;
      document.dispatchEvent(new Event("fullscreenchange"));
    });

    await waitFor(() => {
      const portal = fullscreenContainer.querySelector(
        "[data-testid='glide-data-editor-portal']",
      );
      expect(portal?.parentElement).toBe(fullscreenContainer);
    });

    act(() => {
      fullscreenElement = null;
      document.dispatchEvent(new Event("fullscreenchange"));
    });

    await waitFor(() => {
      const portal = document.body.querySelector(
        "[data-testid='glide-data-editor-portal']",
      );
      expect(portal?.parentElement).toBe(document.body);
    });

    fullscreenContainer.remove();
  });
});
