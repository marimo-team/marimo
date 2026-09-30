/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
} from "@testing-library/react";
import { Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { getNotebook, notebookAtom } from "@/core/cells/cells";
import {
  exportedForTesting,
  flushDocumentChanges,
} from "@/core/cells/document-changes";
import { SETUP_CELL_ID } from "@/core/cells/ids";
import { kernelStateAtom } from "@/core/kernel/state";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import { useConvertCell } from "../useConvertCell";

vi.mock("@/core/runtime/config", () => ({
  useConnectToRuntime: () => vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(() => ({ dismiss: vi.fn() })),
}));

const id = cellId("imports");
const requests = MockRequestClient.create();
const wrapper = ({ children }: PropsWithChildren) => (
  <Provider store={store}>{children}</Provider>
);

beforeEach(() => {
  vi.clearAllMocks();
  store.set(requestClientAtom, requests);
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(kernelStateAtom, { isInstantiated: true, error: null });
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [id]: { name: "imports", code: "import math" } },
    }),
  );
});
afterEach(() => exportedForTesting.cancelPendingChanges());

describe("useConvertCell", () => {
  it("syncs promotion, demotion, and repeated promotion without running code", async () => {
    const { result } = renderHook(useConvertCell, { wrapper });
    await act(() => result.current.convertCell(id));
    expect(getNotebook().cellIds.inOrderIds).toEqual([SETUP_CELL_ID]);
    expect(requests.sendDocumentTransaction).toHaveBeenLastCalledWith({
      syncKernel: true,
      changes: expect.arrayContaining([
        expect.objectContaining({
          type: "create-cell",
          cellId: SETUP_CELL_ID,
          code: "import math",
        }),
        { type: "delete-cell", cellId: id },
      ]),
    });
    await act(() => result.current.convertCell(SETUP_CELL_ID));
    const regularId = getNotebook().cellIds.inOrderIds[0];
    expect(regularId).not.toBe(SETUP_CELL_ID);
    await act(() => result.current.convertCell(regularId));
    expect(getNotebook().cellIds.inOrderIds).toEqual([SETUP_CELL_ID]);
    expect(requests.sendDocumentTransaction).toHaveBeenCalledTimes(3);
    for (const [transaction] of requests.sendDocumentTransaction.mock.calls) {
      expect(transaction.syncKernel).toBe(true);
    }
    expect(requests.sendRun).not.toHaveBeenCalled();
    expect(requests.sendDeleteCell).not.toHaveBeenCalled();
  });

  it("undo restores the original name and ID", async () => {
    const { result } = renderHook(useConvertCell, { wrapper });
    await act(() => result.current.convertCell(id));
    render(
      <TooltipProvider>
        {vi.mocked(toast).mock.calls[0][0].action}
      </TooltipProvider>,
    );
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Undo/ }));
    });
    expect(getNotebook().cellIds.inOrderIds).toEqual([id]);
    expect(getNotebook().cellData[id]).toMatchObject({
      name: "imports",
      code: "import math",
    });
  });

  it("restores the source when the document transaction fails", async () => {
    requests.sendDocumentTransaction.mockRejectedValueOnce(
      new Error("offline"),
    );
    const { result } = renderHook(useConvertCell, { wrapper });
    await act(() => result.current.convertCell(id));
    expect(getNotebook().cellIds.inOrderIds).toEqual([id]);
    expect(getNotebook().cellData[id]).toMatchObject({
      name: "imports",
      code: "import math",
    });
    await expect(flushDocumentChanges()).rejects.toThrow("offline");
    expect(requests.sendDocumentTransaction).toHaveBeenCalledTimes(1);
  });
});
