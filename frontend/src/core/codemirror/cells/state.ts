/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";
import { Facet } from "@codemirror/state";
import type { CellActions } from "@/core/cells/cells";

export interface CodemirrorCellActions extends CellActions {
  toggleHideCode: () => boolean;
  aiCellCompletion: () => boolean;
  createManyBelow: (content: string[]) => void;
  onRun: () => void;
  deleteCell: () => void;
  afterToggleMarkdown: () => void;
}

/**
 * State for cell actions
 */
export const cellActionsState = Facet.define<
  CodemirrorCellActions,
  CodemirrorCellActions
>({
  combine: (values) => values[0],
});

/**
 * State for cell id
 */
export const cellIdState = Facet.define<CellId, CellId>({
  combine: (values) => values[0],
});
