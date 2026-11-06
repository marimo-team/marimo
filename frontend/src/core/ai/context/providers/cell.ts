/* Copyright 2026 Marimo. All rights reserved. */

import { notebookAtom } from "@/core/cells/cells";
import { displayCellName } from "@/core/cells/names";
import type { JotaiStore } from "@/core/state/jotai";
import { AIContextProvider, type AIContextItem } from "../registry";
import { contextToXml } from "../utils";

interface CellContextItem extends AIContextItem {
  type: "cell";
  data: { cellId: string; code: string };
}

export class CellContextProvider extends AIContextProvider<CellContextItem> {
  public readonly title = "Cells";
  public readonly mentionPrefix = "@";
  public readonly contextType = "cell";

  private readonly store: JotaiStore;

  public constructor(store: JotaiStore) {
    super();
    this.store = store;
  }

  public getItems(): CellContextItem[] {
    const notebook = this.store.get(notebookAtom);
    return notebook.cellIds.map((cellId, index) => {
      const cell = notebook.cellData[cellId];
      return {
        uri: this.asURI(cellId),
        name: displayCellName(cell.name, index),
        type: this.contextType,
        description: "Cell code",
        data: { cellId, code: cell.code },
      };
    });
  }

  public formatCompletion(item: CellContextItem) {
    return {
      ...this.createBasicCompletion(item),
      label: `${this.mentionPrefix}${item.name}`,
    };
  }

  public formatContext(item: CellContextItem) {
    return contextToXml({
      type: "cell",
      data: { cellId: item.data.cellId, name: item.name },
      details: item.data.code || "This cell is empty.",
    });
  }
}
