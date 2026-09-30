/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import { SETUP_CELL_ID } from "@/core/cells/ids";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { useCellActionButtons } from "../useCellActionButton";

const { convertCell } = vi.hoisted(() => ({ convertCell: vi.fn() }));
vi.mock("../../cell/useConvertCell", () => ({
  useConvertCell: () => ({ convertCell, converting: false }),
}));

const id = cellId("imports");
const wrapper = ({ children }: PropsWithChildren) => (
  <Provider store={store}>{children}</Provider>
);
const cell = {
  cellId: id,
  name: "imports",
  config: { disabled: false, hide_code: false, column: 0 },
  status: "idle" as const,
  hasOutput: false,
  hasConsoleOutput: false,
  getEditorView: () => null,
};

beforeEach(() => {
  store.set(requestClientAtom, MockRequestClient.create());
  store.set(
    notebookAtom,
    MockNotebook.notebookState({ cellData: { [id]: { code: "import math" } } }),
  );
});

it("offers promotion only when no setup cell exists, and demotion on setup", () => {
  const { result, rerender } = renderHook(
    (cellId) => useCellActionButtons({ cell: { ...cell, cellId } }).flat(),
    { wrapper, initialProps: id },
  );
  const promote = result.current.find(
    (action) => action.label === "Convert to setup cell",
  );
  expect(promote).toBeDefined();
  act(() => {
    promote?.handle();
  });
  expect(convertCell).toHaveBeenCalledWith(id);

  act(() => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [id]: {}, [SETUP_CELL_ID]: { name: "setup" } },
      }),
    );
  });
  expect(
    result.current.some((action) => action.label === "Convert to setup cell"),
  ).toBe(false);
  rerender(SETUP_CELL_ID);
  const demote = result.current.find(
    (action) => action.label === "Convert to regular cell",
  );
  expect(demote).toBeDefined();
  act(() => {
    demote?.handle();
  });
  expect(convertCell).toHaveBeenLastCalledWith(SETUP_CELL_ID);
});

it("disables conversion while another cell is running", () => {
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [id]: {}, [cellId("other")]: {} },
      cellRuntime: { [cellId("other")]: { status: "running" } },
    }),
  );
  const { result } = renderHook(() => useCellActionButtons({ cell }).flat(), {
    wrapper,
  });
  expect(
    result.current.find((action) => action.label === "Convert to setup cell")
      ?.disabled,
  ).toBe(true);
});
