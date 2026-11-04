/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookOutput } from "@marimo-team/client/protocol";
import { renderHook } from "@testing-library/react";
import { atom, createStore } from "jotai";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { DocumentWrapper, mockDocumentModel } from "@/__mocks__/document";
import { partial } from "@/__mocks__/partial";
import { MockRequestClient } from "@/__mocks__/requests";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { toast } from "@/components/ui/use-toast";
import { CellId } from "@/core/cells/ids";
import { requestClientAtom } from "@/core/network/requests";
import type { NotebookReplica } from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { copyToClipboard } from "@/utils/copy";
import type { ActionButton } from "../types";
import { useCellActionButtons } from "../useCellActionButton";

vi.mock("@/utils/copy", () => ({ copyToClipboard: vi.fn() }));
vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));

function renderActions(cellId: CellId, name: string) {
  const store = createStore();
  const { model, documentAtom, stop } = mockDocumentModel(store);
  onTestFinished(stop);
  store.set(requestClientAtom, MockRequestClient.create());
  store.set(
    activeNotebookReplicaAtom,
    partial<NotebookReplica>({
      documentAtom,
      notebookAtom: atom(
        partial<NotebookOutput>({ operations: ["notebook.edit"] }),
      ),
    }),
  );
  const wrapper = ({ children }: { children: ReactNode }) => (
    <DocumentWrapper store={store} model={model}>
      <ModalProvider>{children}</ModalProvider>
    </DocumentWrapper>
  );
  const { result } = renderHook(
    () =>
      useCellActionButtons({
        cell: {
          cellId,
          name,
          config: { disabled: false, hide_code: false, column: null },
          status: "idle",
          blocked: false,
          hasOutput: false,
          hasConsoleOutput: false,
          getEditorView: () => null,
        },
      }),
    { wrapper },
  );
  return result.current;
}

function getAction(groups: ActionButton[][], label: string): ActionButton {
  const action = groups.flat().find((a) => a.label === label);
  if (!action) {
    throw new Error(`Action "${label}" not found`);
  }
  return action;
}

describe("useCellActionButtons", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("places Copy cell ID right after Copy link to cell", () => {
    const groups = renderActions(CellId.create(), "_");
    const linkGroup = groups.find((group) =>
      group.some((a) => a.label === "Copy link to cell"),
    );
    expect(linkGroup?.map((a) => a.label)).toEqual([
      "Name",
      "Copy link to cell",
      "Copy cell ID",
    ]);
  });

  it("copies the cell ID of an unnamed cell", async () => {
    const cellId = CellId.create();
    const groups = renderActions(cellId, "_");

    await getAction(groups, "Copy cell ID").handle();

    expect(copyToClipboard).toHaveBeenCalledWith(cellId);
    expect(toast).toHaveBeenCalledWith({
      description: "Cell ID copied to clipboard",
    });
  });

  it("copies the cell ID, not the name, of a named cell", async () => {
    const cellId = CellId.create();
    const groups = renderActions(cellId, "my_cell");

    await getAction(groups, "Copy cell ID").handle();

    expect(copyToClipboard).toHaveBeenCalledWith(cellId);
  });

  it("keeps Copy link to cell disabled for unnamed cells", () => {
    const groups = renderActions(CellId.create(), "_");

    expect(getAction(groups, "Copy link to cell").disabled).toBe(true);
    expect(getAction(groups, "Copy cell ID").disabled).toBeUndefined();
  });
});
