/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";
import {
  CompactSelection,
  type GridColumn,
  type GridSelection,
  type Rectangle,
} from "@glideapps/glide-data-grid";
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
  getCellContent?: (cell: readonly [number, number]) => Record<string, unknown>;
  customRenderers?: unknown[];
  columns?: readonly GridColumn[];
  gridSelection?: GridSelection;
  onGridSelectionChange?: (selection: GridSelection) => void;
  onHeaderMenuClick?: (col: number, bounds: Rectangle) => void;
  onColumnResize?: (column: GridColumn, newSize: number) => void;
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
  const { CompactSelection } = await vi.importActual<
    typeof import("@glideapps/glide-data-grid")
  >("@glideapps/glide-data-grid");
  return {
    default: React.forwardRef(function MockDataEditor(
      props: MockDataEditorProps,
      _ref: React.Ref<HTMLDivElement>,
    ) {
      captureDataEditorProps(props);
      if (props.gridSelection?.current) {
        props.getCellContent?.(props.gridSelection.current.cell);
      }
      return <div data-testid="mock-data-editor" />;
    }),
    CompactSelection,
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
  DropdownCell: {
    kind: "dropdown-renderer",
    isMatch: (cell: { data: { kind: string } }) =>
      cell.data.kind === "dropdown-cell",
  },
}));

vi.mock("@/theme/useTheme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

const editorProps = {
  data: [{ name: "alice" }],
  columnFields: new Map([["name", "string"]]),
  editableColumns: "all",
  columnTypes: new Map(),
  onAddEdits: vi.fn(),
} satisfies React.ComponentProps<typeof GlideDataEditor>;

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

  it("keeps the grid and selection when cell data changes with the same schema", () => {
    const { rerender } = render(<GlideDataEditor {...editorProps} />);
    const grid = screen.getByTestId("mock-data-editor");
    const selection: GridSelection = {
      columns: CompactSelection.empty(),
      rows: CompactSelection.empty(),
      current: {
        cell: [0, 0],
        range: { x: 0, y: 0, width: 1, height: 1 },
        rangeStack: [],
      },
    };
    act(() =>
      captureDataEditorProps.mock.lastCall?.[0].onGridSelectionChange?.(
        selection,
      ),
    );

    rerender(
      <GlideDataEditor
        {...editorProps}
        data={[{ name: "bob" }]}
        columnFields={new Map(editorProps.columnFields)}
      />,
    );

    expect(screen.getByTestId("mock-data-editor")).toBe(grid);
    expect(captureDataEditorProps.mock.lastCall?.[0].gridSelection).toEqual(
      selection,
    );
    expect(capturedDataEditor.getCellContent?.([0, 0])).toMatchObject({
      data: "bob",
    });
  });

  it.each([
    { operation: "remove", names: ["name"] },
    { operation: "rename", names: ["name", "weekday"] },
    { operation: "insert", names: ["name", "day", "extra"] },
    { operation: "reorder", names: ["day", "name"] },
  ])(
    "preserves widths and resets selection, menu, and grid on column $operation",
    ({ names }) => {
      const columnFields = new Map<string, "string">([
        ["name", "string"],
        ["day", "string"],
      ]);
      const props = {
        ...editorProps,
        columnFields,
        data: [{ name: "alice", day: "Friday" }],
      };
      const { rerender } = render(<GlideDataEditor {...props} />);
      const grid = screen.getByTestId("mock-data-editor");
      act(() => {
        captureDataEditorProps.mock.lastCall?.[0].onColumnResize?.(
          { title: "name", width: 100 },
          240,
        );
      });
      expect(
        captureDataEditorProps.mock.lastCall?.[0].columns?.[0],
      ).toMatchObject({ width: 240 });
      act(() => {
        captureDataEditorProps.mock.lastCall?.[0].onGridSelectionChange?.({
          columns: CompactSelection.fromSingleSelection(1),
          rows: CompactSelection.fromSingleSelection(0),
          current: {
            cell: [1, 0],
            range: { x: 1, y: 0, width: 1, height: 1 },
            rangeStack: [],
          },
        });
        captureDataEditorProps.mock.lastCall?.[0].onHeaderMenuClick?.(1, {
          x: 0,
          y: 0,
          width: 100,
          height: 30,
        });
      });
      expect(screen.getByText("Copy column name")).toBeInTheDocument();
      captureDataEditorProps.mockClear();

      const nextFields = new Map<string, "string">(
        names.map((name) => [name, "string"]),
      );
      rerender(<GlideDataEditor {...props} columnFields={nextFields} />);

      expect(screen.getByTestId("mock-data-editor")).not.toBe(grid);
      expect(screen.queryByText("Copy column name")).toBeNull();
      for (const [rendered] of captureDataEditorProps.mock.calls) {
        expect(rendered.gridSelection).toEqual({
          columns: CompactSelection.empty(),
          rows: CompactSelection.empty(),
        });
        expect(rendered.columns?.map((column) => column.title)).toEqual([
          ...nextFields.keys(),
        ]);
        expect(
          rendered.columns?.find((column) => column.title === "name"),
        ).toMatchObject({ width: 240 });
      }
    },
  );

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
      { kind: "dropdown-renderer", isMatch: expect.any(Function) },
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
