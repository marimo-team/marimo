/* Copyright 2026 Marimo. All rights reserved. */

import type { OnChangeFn, RowSelectionState } from "@tanstack/react-table";
import { ColumnsIcon, RowsIcon } from "lucide-react";
import type React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  GetRowResult,
  PreviewColumn,
} from "@/plugins/impl/DataTablePlugin";
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

  // Single panel — no tabs needed
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
      className="h-full flex flex-col min-w-[350px]"
    >
      <TabsList className="mx-2 mt-2 p-2 shrink-0 w-auto">
        <TabsTrigger
          value={PANEL_TYPES.ROW_VIEWER}
          className="py-1.5 px-5 text-xs uppercase tracking-wide font-bold flex-1 flex items-center justify-center gap-1"
        >
          <RowsIcon className="w-3 h-3" />
          Rows
        </TabsTrigger>
        <TabsTrigger
          value={PANEL_TYPES.COLUMN_EXPLORER}
          className="py-1.5 px-5 text-xs uppercase tracking-wide font-bold flex-1 flex items-center justify-center gap-1"
        >
          <ColumnsIcon className="w-3 h-3" />
          Columns
        </TabsTrigger>
      </TabsList>

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
