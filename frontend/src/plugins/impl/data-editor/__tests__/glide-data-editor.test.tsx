/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GlideDataEditor } from "../glide-data-editor";

interface MockDataEditorProps {
  portalElementRef?: React.RefObject<HTMLElement>;
  onCellEdited?: (
    cell: [number, number],
    value: { data: unknown; kind?: unknown },
  ) => void;
  onRowAppended?: () => void;
  getCellContent?: (cell: [number, number]) => Record<string, unknown>;
  customRenderers?: unknown[];
}

const captureDataEditorProps = vi.hoisted(() =>
  vi.fn<(props: MockDataEditorProps) => void>(),
);

const capturedDataEditor = {
  get ref() {
    return captureDataEditorProps.mock.lastCall?.[0].portalElementRef;
  },
  get onCellEdited() {
    return captureDataEditorProps.mock.lastCall?.[0].onCellEdited;
  },
  get onRowAppended() {
    return captureDataEditorProps.mock.lastCall?.[0].onRowAppended;
  },
  get getCellContent() {
    return captureDataEditorProps.mock.lastCall?.[0].getCellContent;
  },
  get customRenderers() {
    return captureDataEditorProps.mock.lastCall?.[0].customRenderers;
  },
};

vi.mock("@glideapps/glide-data-grid", async () => {
  const React = await import("react");
  return {
    default: React.forwardRef(function MockDataEditor(
      props: MockDataEditorProps,
      _ref: React.Ref<HTMLDivElement>,
    ) {
      captureDataEditorProps(props);
      return <div data-testid="mock-data-editor" />;
    }),
    CompactSelection: {
      empty: () => ({}),
    },
    GridCellKind: {
      Text: "text",
      Number: "number",
      Boolean: "boolean",
      Custom: "custom",
    },
    GridColumnIcon: {
      ProtectedColumnOverlay: "protected",
    },
  };
});

vi.mock("@glideapps/glide-data-grid-cells", () => ({
  DropdownCell: { kind: "dropdown-renderer" },
}));

vi.mock("@/theme/useTheme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

const editorProps = {
  data: [{ name: "alice" }],
  columnFields: new Map([["name", "string"]]) as Map<string, "string">,
  editableColumns: "all" as const,
  columnTypes: new Map(),
  onAddEdits: vi.fn(),
};

describe("GlideDataEditor portal", () => {
  let fullscreenElement: Element | null;

  beforeEach(() => {
    vi.clearAllMocks();
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
    expect(capturedDataEditor.ref).toBeDefined();
    await waitFor(() => {
      expect(capturedDataEditor.ref?.current).toBe(portal);
    });
  });

  it("emits cell edits", () => {
    const onAddEdits = vi.fn();
    render(
      <TooltipProvider>
        <GlideDataEditor {...editorProps} onAddEdits={onAddEdits} />
      </TooltipProvider>,
    );

    act(() => capturedDataEditor.onCellEdited?.([0, 0], { data: "bob" }));

    expect(onAddEdits).toHaveBeenCalledWith([
      { rowIdx: 0, columnId: "name", value: "bob" },
    ]);
  });

  it("creates a restricted dropdown cell and registers only its renderer", () => {
    render(
      <TooltipProvider>
        <GlideDataEditor
          {...editorProps}
          columnTypes={new Map([["name", ["alice", "bob"]]])}
        />
      </TooltipProvider>,
    );

    expect(capturedDataEditor.getCellContent?.([0, 0])).toMatchObject({
      kind: "custom",
      copyData: "alice",
      data: {
        kind: "dropdown-cell",
        value: "alice",
        allowedValues: ["alice", "bob"],
      },
    });
    expect(capturedDataEditor.customRenderers).toEqual([
      { kind: "dropdown-renderer" },
    ]);
  });

  it("emits the selected dropdown value and rejects an invalid empty edit", () => {
    const onAddEdits = vi.fn();
    render(
      <TooltipProvider>
        <GlideDataEditor
          {...editorProps}
          columnTypes={new Map([["name", ["alice", "bob"]]])}
          onAddEdits={onAddEdits}
        />
      </TooltipProvider>,
    );

    act(() =>
      capturedDataEditor.onCellEdited?.([0, 0], {
        kind: "custom",
        data: { kind: "dropdown-cell", value: "bob" },
      }),
    );
    act(() =>
      capturedDataEditor.onCellEdited?.([0, 0], {
        kind: "custom",
        data: { kind: "dropdown-cell", value: "" },
      }),
    );

    expect(onAddEdits).toHaveBeenCalledTimes(1);
    expect(onAddEdits).toHaveBeenCalledWith([
      { rowIdx: 0, columnId: "name", value: "bob" },
    ]);
  });

  it("uses the first dropdown option when appending a row", () => {
    const onAddEdits = vi.fn();
    render(
      <TooltipProvider>
        <GlideDataEditor
          {...editorProps}
          columnTypes={new Map([["name", ["first", "second"]]])}
          onAddEdits={onAddEdits}
        />
      </TooltipProvider>,
    );

    act(() => capturedDataEditor.onRowAppended?.());

    expect(onAddEdits).toHaveBeenCalledWith([
      { rowIdx: 1, columnId: "name", value: "first" },
    ]);
  });

  it("normalizes edits for a configured boolean column", () => {
    const onAddEdits = vi.fn();
    render(
      <TooltipProvider>
        <GlideDataEditor
          {...editorProps}
          data={[{ active: false }]}
          columnFields={new Map([["active", "boolean" as const]])}
          columnTypes={new Map([["active", "boolean" as const]])}
          onAddEdits={onAddEdits}
        />
      </TooltipProvider>,
    );

    act(() => capturedDataEditor.onCellEdited?.([0, 0], { data: "YES" }));

    expect(onAddEdits).toHaveBeenCalledWith([
      { rowIdx: 0, columnId: "active", value: true },
    ]);
  });

  it("emits one positional edit per cell when appending a row", () => {
    const onAddEdits = vi.fn();
    render(
      <TooltipProvider>
        <GlideDataEditor {...editorProps} onAddEdits={onAddEdits} />
      </TooltipProvider>,
    );

    act(() => capturedDataEditor.onRowAppended?.());

    expect(onAddEdits).toHaveBeenCalledWith([
      { rowIdx: 1, columnId: "name", value: "" },
    ]);
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

  it("unmounts cleanly while fullscreen is active", async () => {
    const fullscreenContainer = document.createElement("div");
    document.body.appendChild(fullscreenContainer);

    const { unmount } = render(
      <TooltipProvider>
        <GlideDataEditor {...editorProps} />
      </TooltipProvider>,
    );

    act(() => {
      fullscreenElement = fullscreenContainer;
      document.dispatchEvent(new Event("fullscreenchange"));
    });

    await waitFor(() => {
      expect(
        fullscreenContainer.querySelector(
          "[data-testid='glide-data-editor-portal']",
        ),
      ).not.toBeNull();
    });

    expect(() => {
      act(() => unmount());
    }).not.toThrow();

    expect(
      fullscreenContainer.querySelector(
        "[data-testid='glide-data-editor-portal']",
      ),
    ).toBeNull();
    expect(
      document.body.querySelector("[data-testid='glide-data-editor-portal']"),
    ).toBeNull();

    fullscreenContainer.remove();
  });
});
