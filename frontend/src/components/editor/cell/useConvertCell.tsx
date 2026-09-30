/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import useEvent from "react-use-event-hook";
import { UndoButton } from "@/components/buttons/undo-button";
import { toast } from "@/components/ui/use-toast";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import { flushDocumentChanges } from "@/core/cells/document-changes";
import { CellId, SETUP_CELL_ID } from "@/core/cells/ids";
import { notebookQueueOrRunningCount } from "@/core/cells/utils";
import { waitForKernelToBeInstantiated } from "@/core/kernel/state";
import { waitForConnectionOpen } from "@/core/network/connection";
import { useConnectToRuntime } from "@/core/runtime/config";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";

const convertingCellAtom = atom(false);

export function useConvertCell() {
  const { convertCell } = useCellActions();
  const converting = useAtomValue(convertingCellAtom);
  const connect = useConnectToRuntime();

  const convert = useEvent(async function convert(
    cellId: CellId,
    undo?: Parameters<typeof convertCell>[0],
  ) {
    if (store.get(convertingCellAtom)) {
      return;
    }
    store.set(convertingCellAtom, true);
    let rollback: Parameters<typeof convertCell>[0] | undefined;
    try {
      await connect();
      await waitForConnectionOpen();
      await waitForKernelToBeInstantiated();
      // Flush earlier edits before changing the local cell identity.
      await flushDocumentChanges();
      const notebook = getNotebook();
      const ids = notebook.cellIds.inOrderIds;
      const newCellId =
        undo?.newCellId ??
        (cellId === SETUP_CELL_ID ? CellId.create() : SETUP_CELL_ID);
      if (
        !ids.includes(cellId) ||
        ids.includes(newCellId) ||
        notebookQueueOrRunningCount(notebook) > 0
      ) {
        return;
      }
      const cell = notebook.cellData[cellId];
      const column = notebook.cellIds.findWithId(cellId);
      rollback = {
        cellId: newCellId,
        newCellId: cellId,
        restore: {
          name: cell.name,
          config: cell.config,
          columnId: column.id,
          index: column.indexOfOrThrow(cellId),
        },
      };
      convertCell(undo ?? { cellId, newCellId });
      await flushDocumentChanges();
      if (!undo) {
        const restore = rollback;
        const { dismiss } = toast({
          title:
            newCellId === SETUP_CELL_ID
              ? "Converted to setup cell"
              : "Converted to regular cell",
          description: "Run the cell to apply the change.",
          action: (
            <UndoButton
              onClick={() => {
                void convert(newCellId, restore);
                dismiss();
              }}
            />
          ),
        });
      }
    } catch (error) {
      if (rollback) {
        convertCell(rollback);
      }
      Logger.error("Failed to convert cell", error);
    } finally {
      store.set(convertingCellAtom, false);
    }
  });

  return { convertCell: (cellId: CellId) => convert(cellId), converting };
}
