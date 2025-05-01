/* Copyright 2024 Marimo. All rights reserved. */

import { DataSelectionPanel as SelectionPanel } from "@/components/data-table/selection-panel/data-selection";

export const DataSelectionPanel: React.FC<{
  handleDragging: (isDragging: boolean) => void;
}> = ({ handleDragging }) => {
  return <SelectionPanel handleDragging={handleDragging} />;
};
