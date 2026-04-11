/* Copyright 2026 Marimo. All rights reserved. */

import { Fill } from "@marimo-team/react-slotz";
import type { OnChangeFn, RowSelectionState } from "@tanstack/react-table";
import type React from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { SlotNames } from "@/core/slots/slots";
import type {
  GetRowResult,
  PreviewColumn,
} from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import {
  PANEL_TYPES,
  type PanelType,
} from "../../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { ColumnExplorerPanel } from "../column-explorer-panel/column-explorer";
import { RowViewerPanel } from "../row-viewer-panel/row-viewer";
import type { FieldTypesWithExternalType, TooManyRows } from "../types";

export interface TableExplorerPanelProps {
  // Row viewer props
  rowIdx: number;
  setRowIdx: (rowIdx: number) => void;
  totalRows: number | TooManyRows;
  fieldTypes: FieldTypesWithExternalType | undefined | null;
  getRow: (rowIdx: number) => Promise<GetRowResult>;
  isSelectable: boolean;
  isRowSelected: boolean;
  handleRowSelectionChange?: OnChangeFn<RowSelectionState>;
  // Column explorer props
  previewColumn?: PreviewColumn;
  totalColumns: number;
  tableId: string;
  // Visibility flags
  showRowExplorer: boolean;
  showColumnExplorer: boolean;
  // Tab state (driven by contextAwarePanelType atom)
  activeTab: PanelType | null;
  onTabChange: (tab: PanelType) => void;
}

const tabTriggerClassName =
  "text-[13px] uppercase tracking-wide font-semibold cursor-pointer transition-colors";
const activeClassName = "text-primary";
const inactiveClassName = "hover:text-foreground";

export const TableExplorerPanel: React.FC<TableExplorerPanelProps> = ({
  // Row viewer
  rowIdx,
  setRowIdx,
  totalRows,
  fieldTypes,
  getRow,
  isSelectable,
  isRowSelected,
  handleRowSelectionChange,
  // Column explorer
  previewColumn,
  totalColumns,
  tableId,
  // Visibility
  showRowExplorer,
  showColumnExplorer,
  // Tab state
  activeTab,
  onTabChange,
}) => {
  const showTabs = showRowExplorer && showColumnExplorer;

  const rowViewer = (
    <RowViewerPanel
      rowIdx={rowIdx}
      setRowIdx={setRowIdx}
      totalRows={totalRows}
      fieldTypes={fieldTypes}
      getRow={getRow}
      isSelectable={isSelectable}
      isRowSelected={isRowSelected}
      handleRowSelectionChange={handleRowSelectionChange}
    />
  );

  const columnExplorer = previewColumn && (
    <ColumnExplorerPanel
      previewColumn={previewColumn}
      fieldTypes={fieldTypes}
      totalRows={totalRows}
      totalColumns={totalColumns}
      tableId={tableId}
    />
  );

  // If only one panel is visible, don't show tabs
  if (!showTabs) {
    if (showRowExplorer) {
      return rowViewer;
    }
    if (showColumnExplorer) {
      return columnExplorer;
    }
    return null;
  }

  // Resolve active tab — fall back to first available
  const resolvedTab = activeTab ?? PANEL_TYPES.ROW_VIEWER;

  return (
    <Tabs
      value={resolvedTab}
      onValueChange={(value) => onTabChange(value as PanelType)}
      className="flex flex-col min-w-[350px]"
    >
      <Fill name={SlotNames.CONTEXT_AWARE_PANEL_HEADER}>
        <div className="flex items-center gap-1">
          <Button
            variant="text"
            size="xs"
            onClick={() => onTabChange(PANEL_TYPES.ROW_VIEWER)}
            className={cn(
              tabTriggerClassName,
              resolvedTab === PANEL_TYPES.ROW_VIEWER
                ? activeClassName
                : inactiveClassName,
            )}
          >
            Rows
          </Button>
          <span className="text-muted-foreground text-xs">|</span>
          <Button
            variant="text"
            size="xs"
            onClick={() => onTabChange(PANEL_TYPES.COLUMN_EXPLORER)}
            className={cn(
              tabTriggerClassName,
              resolvedTab === PANEL_TYPES.COLUMN_EXPLORER
                ? activeClassName
                : inactiveClassName,
            )}
          >
            Columns
          </Button>
        </div>
      </Fill>

      <TabsContent
        value={PANEL_TYPES.ROW_VIEWER}
        className="flex-1 overflow-auto"
      >
        {rowViewer}
      </TabsContent>
      <TabsContent
        value={PANEL_TYPES.COLUMN_EXPLORER}
        className="flex-1 overflow-auto"
      >
        {columnExplorer}
      </TabsContent>
    </Tabs>
  );
};
