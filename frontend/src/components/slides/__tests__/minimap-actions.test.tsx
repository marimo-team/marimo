/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import { MultiColumn } from "@/utils/id-tree";
import { SlidesMinimap } from "../minimap";

const A = cellId("a");
const B = cellId("b");

// Spies shared with the hoisted module mocks below.
const { createNewCell, deleteCell, moveCellToIndex } = vi.hoisted(() => ({
  createNewCell: vi.fn(),
  deleteCell: vi.fn(),
  moveCellToIndex: vi.fn(),
}));

vi.mock("@/core/cells/cells", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/core/cells/cells")>();
  return {
    ...actual,
    useCellActions: () => ({ moveCellToIndex, createNewCell }),
    useCellIds: () => MultiColumn.from([[A, B]]),
  };
});

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => deleteCell,
}));

beforeAll(() => {
  // jsdom doesn't implement these; radix menus poke at them.
  global.HTMLElement.prototype.scrollIntoView = () => {
    /* noop */
  };
  if (!global.HTMLElement.prototype.hasPointerCapture) {
    global.HTMLElement.prototype.hasPointerCapture = () => false;
  }
  if (!global.HTMLElement.prototype.releasePointerCapture) {
    global.HTMLElement.prototype.releasePointerCapture = () => {
      /* noop */
    };
  }
  global.IntersectionObserver ??= class {
    observe() {
      /* noop */
    }
    unobserve() {
      /* noop */
    }
    disconnect() {
      /* noop */
    }
    takeRecords() {
      return [];
    }
    root = null;
    rootMargin = "";
    thresholds = [];
  } as unknown as typeof IntersectionObserver;
});

// The minimap only reads `id`/`code`/`status`/`output`, so a minimal stub is
// enough; the cast is confined to this helper.
function makeCell(id: CellId): CellRuntimeState & CellData {
  return {
    id,
    code: `print("${id}")`,
    output: null,
    status: "idle",
  } as unknown as CellRuntimeState & CellData;
}

function renderMinimap() {
  const onSlideClick = vi.fn();
  const utils = render(
    <TooltipProvider>
      <SlidesMinimap
        cells={[makeCell(A), makeCell(B)]}
        thumbnailWidth={200}
        canReorder={false}
        activeCellId={null}
        onSlideClick={onSlideClick}
      />
    </TooltipProvider>,
  );
  return { ...utils, onSlideClick };
}

const EMPTY_CELL = { code: "", autoFocus: false } as const;

describe("SlidesMinimap insert lines", () => {
  it("inserts a blank cell above the first row and below any row", () => {
    renderMinimap();
    // First row exposes both an above and a below line; later rows only below.
    // DOM order: [A-above, A-below, B-below].
    const inserts = screen.getAllByTestId("minimap-insert-cell");
    expect(inserts).toHaveLength(3);

    fireEvent.click(inserts[0]);
    expect(createNewCell).toHaveBeenLastCalledWith({
      cellId: A,
      before: true,
      ...EMPTY_CELL,
    });

    fireEvent.click(inserts[1]);
    expect(createNewCell).toHaveBeenLastCalledWith({
      cellId: A,
      before: false,
      ...EMPTY_CELL,
    });

    fireEvent.click(inserts[2]);
    expect(createNewCell).toHaveBeenLastCalledWith({
      cellId: B,
      before: false,
      ...EMPTY_CELL,
    });
  });
});

describe("SlidesMinimap context menu", () => {
  const openRowMenu = (container: HTMLElement, id: CellId) => {
    const row = container.querySelector<HTMLElement>(`[data-cell-id="${id}"]`);
    expect(row).not.toBeNull();
    fireEvent.contextMenu(row!);
  };

  it('"Add cell" inserts a blank cell below the row', () => {
    const { container } = renderMinimap();
    openRowMenu(container, A);
    fireEvent.click(screen.getByText("Add cell"));
    expect(createNewCell).toHaveBeenCalledWith({
      cellId: A,
      before: false,
      ...EMPTY_CELL,
    });
  });

  it('"Delete cell" deletes the row\'s cell', () => {
    const { container } = renderMinimap();
    openRowMenu(container, B);
    fireEvent.click(screen.getByText("Delete cell"));
    expect(deleteCell).toHaveBeenCalledWith({ cellId: B });
  });
});

describe("SlidesMinimap keyboard activation", () => {
  it("activates the row on Enter but ignores Space (reserved by reveal.js)", () => {
    const { container, onSlideClick } = renderMinimap();
    const row = container.querySelector<HTMLElement>(`[data-cell-id="${A}"]`);
    expect(row).not.toBeNull();

    fireEvent.keyDown(row!, { key: "Enter" });
    expect(onSlideClick).toHaveBeenCalledWith(0);

    onSlideClick.mockClear();
    fireEvent.keyDown(row!, { key: " " });
    expect(onSlideClick).not.toHaveBeenCalled();
  });
});
