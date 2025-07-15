/* Copyright 2024 Marimo. All rights reserved. */

import DataEditor, {
  CompactSelection,
  type DataEditorRef,
  type EditableGridCell,
  type GridCell,
  GridCellKind,
  type GridColumn,
  type GridKeyEventArgs,
  type GridSelection,
  type Item,
  type Rectangle,
} from "@glideapps/glide-data-grid";
import { CopyIcon, TrashIcon } from "lucide-react";
import React, { useCallback, useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import type { FieldTypes } from "@/components/data-table/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/theme/useTheme";
import { copyToClipboard } from "@/utils/copy";
import {
  getColumnHeaderIcon,
  getColumnKind,
  isColumnEdit,
  isPositionalEdit,
  isRowEdit,
  pasteCells,
} from "./glide-utils";
import { getGlideTheme } from "./themes";
import { BulkEdit, type Edits, type ModifiedGridColumn } from "./types";
import "@glideapps/glide-data-grid/dist/index.css"; // TODO: We are reimporting this
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import type { DataType } from "@/core/kernel/messages";
import { useOnMount } from "@/hooks/useLifecycle";
import { useNonce } from "@/hooks/useNonce";
import { logNever } from "@/utils/assertNever";
import { Events } from "@/utils/events";
import { AddColumnSub, RenameColumnSub } from "./components";
import {
  insertColumn,
  modifyColumnFields,
  removeColumn,
  renameColumn,
} from "./data-utils";

interface GlideDataEditorProps<T> {
  data: T[];
  setData: (data: T[] | ((prev: T[]) => T[])) => void;
  columnFields: FieldTypes;
  setColumnFields: React.Dispatch<React.SetStateAction<FieldTypes>>;
  edits: Edits["edits"];
  onAddEdits: (edits: Edits["edits"]) => void;
  onAddRows: (newRows: object[]) => void;
  onDeleteRows: (rows: number[]) => void;
  onRenameColumn: (columnIdx: number, newName: string) => void;
  onDeleteColumn: (columnIdx: number) => void;
  onAddColumn: (columnIdx: number, newName: string) => void;
}

export const GlideDataEditor = <T,>({
  data,
  setData,
  columnFields,
  setColumnFields,
  edits,
  onAddEdits,
  onAddRows,
  onDeleteRows,
  onRenameColumn,
  onDeleteColumn,
  onAddColumn,
}: GlideDataEditorProps<T>) => {
  const { theme } = useTheme();
  const dataEditorRef = useRef<DataEditorRef>(null);

  const [menu, setMenu] = useState<{ col: number; bounds: Rectangle }>();
  const [showSearch, setShowSearch] = useState<boolean>(false);
  const [selection, setSelection] = React.useState<GridSelection>({
    columns: CompactSelection.empty(),
    rows: CompactSelection.empty(),
  });

  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const rerender = useNonce();

  // Handle initial edits passed in
  useOnMount(() => {
    if (edits.length === 0) {
      return;
    }

    // Group edits by row index to build new rows
    const newRows = new Map<number, Record<string, unknown>>();

    for (const edit of edits) {
      if (isPositionalEdit(edit)) {
        if (edit.rowIdx >= data.length) {
          // This is a new row
          if (!newRows.has(edit.rowIdx)) {
            newRows.set(edit.rowIdx, {});
          }
          const row = newRows.get(edit.rowIdx);
          if (row) {
            row[edit.columnId] = edit.value;
          }
        } else {
          // This is an existing row, update the data
          setData((prev) => {
            const newData = [...prev];
            newData[edit.rowIdx][edit.columnId as keyof T] =
              edit.value as T[keyof T];
            return newData;
          });
        }
      } else if (isRowEdit(edit) && edit.type === BulkEdit.Remove) {
        // Add rows is currently handled under positional edits, so we only cover deletes here
        setData((prev) => prev.filter((_, i) => i !== edit.rowIdx));
      } else if (isColumnEdit(edit)) {
        switch (edit.type) {
          case BulkEdit.Remove:
            // Remove the column from the data
            setData((prev) => removeColumn(prev, edit.columnIdx));
            setColumnFields((prev) =>
              modifyColumnFields({
                columnFields: prev,
                columnIdx: edit.columnIdx,
                type: "remove",
              }),
            );
            break;
          case BulkEdit.Insert:
            setColumnFields((prev) =>
              modifyColumnFields({
                columnFields: prev,
                columnIdx: edit.columnIdx,
                type: "insert",
                newColumnName: edit.newName,
              }),
            );
            setData((prev) => insertColumn(prev, edit.newName));
            break;
          case BulkEdit.Rename: {
            const oldName = columns[edit.columnIdx].title;
            const newName = edit.newName;
            if (!oldName || !newName) {
              return;
            }

            setColumnFields((prev) =>
              modifyColumnFields({
                columnFields: prev,
                columnIdx: edit.columnIdx,
                type: "rename",
                newColumnName: newName,
              }),
            );

            setData((prev) => renameColumn(prev, oldName, newName));
            break;
          }
        }
      }
    }

    // Add new rows in order
    const sortedNewRows = [...newRows.entries()]
      .sort(([a], [b]) => a - b)
      .map(([, row]) => row);

    if (sortedNewRows.length > 0) {
      setData((prev) => [...prev, ...(sortedNewRows as T[])]);
    }

    // Force re-render to update the total rows
    rerender();
  });

  const columns: ModifiedGridColumn[] = useMemo(() => {
    const columns: ModifiedGridColumn[] = [];
    for (const [columnName, fieldType] of Object.entries(columnFields)) {
      columns.push({
        id: columnName,
        title: columnName,
        width: columnWidths[columnName], // Enables resizing
        icon: getColumnHeaderIcon(fieldType),
        kind: getColumnKind(fieldType),
        dataType: fieldType,
        hasMenu: true,
      });
    }

    return columns;
  }, [columnFields, columnWidths]);

  const getCellContent = useCallback(
    (cell: Item): GridCell => {
      const [col, row] = cell;
      const dataRow = data[row];

      const dataItem = dataRow[columns[col].title as keyof T];
      const columnKind = columns[col].kind;

      if (columnKind === GridCellKind.Boolean) {
        const value = Boolean(dataItem);
        return {
          kind: GridCellKind.Boolean,
          allowOverlay: false,
          readonly: false,
          data: value,
        };
      }

      if (columnKind === GridCellKind.Number && typeof dataItem === "number") {
        return {
          kind: GridCellKind.Number,
          allowOverlay: true,
          readonly: false,
          displayData: String(dataItem),
          data: dataItem,
        };
      }

      return {
        kind: GridCellKind.Text,
        allowOverlay: true,
        readonly: false,
        displayData: String(dataItem),
        data: String(dataItem),
      };
    },
    [columns, data],
  );

  const onCellEdited = useCallback(
    (cell: Item, newValue: EditableGridCell) => {
      const [col, row] = cell;
      const column = columns[col];
      const key = column.title;

      // Deletes are not handled by validateCell, so we need to handle them here
      let newData = newValue.data;
      if (
        (column.dataType === "number" || column.dataType === "integer") &&
        (newValue.data === undefined || newValue.data === "")
      ) {
        newData = null;
      }

      setData((prev) => {
        const data = [...prev];
        data[row][key as keyof T] = newData as T[keyof T];
        return data;
      });

      onAddEdits([{ rowIdx: row, columnId: key, value: newData }]);
    },
    [columns, onAddEdits, setData],
  );

  const onColumnResize = useCallback((column: GridColumn, newSize: number) => {
    setColumnWidths((prev) => ({
      ...prev,
      [column.title]: newSize,
    }));
  }, []);

  // Only called when user edits a cell, not deletes
  const validateCell = useCallback(
    (cell: Item, newValue: EditableGridCell, _prevValue: GridCell): boolean => {
      const [col, _row] = cell;
      const key = columns[col].title;

      const columnType = columnFields[key];
      // Verify the new value is of the correct type
      switch (columnType) {
        case "number":
        case "integer":
          if (Number.isNaN(Number(newValue.data))) {
            return false;
          }
          break;
        case "boolean":
          if (typeof newValue.data !== "boolean") {
            return false;
          }
          break;
      }

      return true;
    },
    [columnFields, columns],
  );

  // Hack to emit copy event as these events aren't triggered automatically in shadow DOM
  // Paste event does not work so we manually handle it
  const onKeyDown = useCallback(
    (e: GridKeyEventArgs) => {
      if (!dataEditorRef.current) {
        return;
      }

      if (Events.isMetaOrCtrl(e) && e.key === "c") {
        dataEditorRef.current.emit("copy");
        return;
      }

      if (Events.isMetaOrCtrl(e) && e.key === "v") {
        pasteCells({
          selection,
          data,
          setData,
          columns,
          onAddEdits,
        });
        return;
      }

      if (Events.isMetaOrCtrl(e) && e.key === "f") {
        setShowSearch((prev) => !prev);
        e.stopPropagation();
        e.preventDefault();
        return;
      }

      if (e.key === "Escape") {
        setShowSearch(false);
        return;
      }
    },
    [columns, data, onAddEdits, selection, setData],
  );

  const onRowAppend = useCallback(() => {
    const newRow: Record<string, unknown> = Object.fromEntries(
      columns.map((column) => {
        const dataType = column.dataType;
        switch (dataType) {
          case "boolean":
            return [column.title, false];
          case "number":
          case "integer":
            return [column.title, null];
          case "date":
          case "datetime":
          case "time":
            // TODO: Handle specific types
            return [column.title, new Date()];
          case "string":
          case "unknown":
            return [column.title, ""];
          default:
            logNever(dataType);
            return [column.title, ""];
        }
      }),
    );
    onAddRows([newRow]);

    // Update data
    setData((prev) => [...prev, newRow as T]);
  }, [columns, onAddRows, setData]);

  const handleDeleteRows = () => {
    const rows = selection.rows.toArray();
    onDeleteRows(rows);

    let index = 0;
    for (const row of rows) {
      const adjustedRow = row - index; // Adjust for previously deleted rows
      setData((prev) => prev.filter((_, i) => i !== adjustedRow));
      index++;
    }

    // Clear selection
    setSelection({
      columns: CompactSelection.empty(),
      rows: CompactSelection.empty(),
    });
  };

  const onHeaderMenuClick = useEvent((col: number, bounds: Rectangle) => {
    setMenu({ col, bounds });
  });

  const handleCopyColumnName = async () => {
    if (menu) {
      const columnName = columns[menu.col].title;
      await copyToClipboard(columnName);
      setMenu(undefined);
    }
  };

  function toastColumnExists(name: string) {
    toast({
      title: `Column '${name}' already exists`,
      description: "Please enter a different column name",
      variant: "danger",
    });
  }

  const handleRenameColumn = (newName: string) => {
    if (menu) {
      const oldColumnName = columns[menu.col].title;

      // Validate the new column name
      if (columnFields[newName]) {
        toastColumnExists(newName);
        return;
      }

      const dataType = columns[menu.col].dataType;

      onRenameColumn(menu.col, newName);
      setColumnFields((prev) =>
        modifyColumnFields({
          columnFields: prev,
          columnIdx: menu.col,
          type: "rename",
          dataType,
          newColumnName: newName,
        }),
      );

      // Update the data
      setData((prev) => renameColumn(prev, oldColumnName, newName));
      setMenu(undefined);
    }
  };

  const handleDeleteColumn = () => {
    if (menu) {
      onDeleteColumn(menu.col);
      setColumnFields((prev) =>
        modifyColumnFields({
          columnFields: prev,
          columnIdx: menu.col,
          type: "remove",
        }),
      );

      setData((prev) => removeColumn(prev, menu.col));
      setMenu(undefined);
    }
  };

  const handleAddColumn = (options: {
    direction: "left" | "right";
    columnName: string;
    dataType: DataType;
  }) => {
    const { direction, columnName, dataType } = options;

    if (menu) {
      const columnIdx = menu.col + (direction === "left" ? 0 : 1);
      // Clamp to 0 and length of columns
      const clampedColumnIdx = Math.max(0, Math.min(columnIdx, columns.length));

      // Validate the new column name
      if (columnFields[columnName]) {
        toastColumnExists(columnName);
        return;
      }

      onAddColumn(clampedColumnIdx, columnName);

      setColumnFields((prev) =>
        modifyColumnFields({
          columnFields: prev,
          columnIdx: clampedColumnIdx,
          type: "insert",
          dataType,
          newColumnName: columnName,
        }),
      );

      // Update the data - add the new column to all rows,
      // ordering does not matter as we call getCellContent based on columnTitle
      setData((prev) => insertColumn(prev, columnName));
      setMenu(undefined);
    }
  };

  const isLastColumn = menu?.col === columns.length - 1;

  // There is a guarantee that only one column's menu is open (as interaction is disabled outside of the menu)
  const isMenuOpen = menu !== undefined;
  const iconClassName = "mr-2 h-3.5 w-3.5";

  const trailingRowOptions = {
    hint: "New row",
    sticky: true,
    tint: true,
  };

  const isLargeDataset = data.length > 100_000;

  const renderDropdownMenu = () => {
    if (!isMenuOpen) {
      return;
    }

    const bulkEditItems = (
      <>
        <RenameColumnSub
          currentColumnName={columns[menu.col].title}
          onRename={handleRenameColumn}
          onCancel={() => setMenu(undefined)}
        />

        <DropdownMenuSeparator />

        <AddColumnSub
          direction="left"
          onAdd={(columnName, dataType) =>
            handleAddColumn({ direction: "left", columnName, dataType })
          }
          onCancel={() => setMenu(undefined)}
        />

        <AddColumnSub
          direction="right"
          onAdd={(columnName, dataType) =>
            handleAddColumn({ direction: "right", columnName, dataType })
          }
          onCancel={() => setMenu(undefined)}
        />

        <DropdownMenuSeparator />

        {/* There is a bug `undefined (reading 'headerRowMarkerDisabled')` when deleting the last column. So we temporarily disable it. */}
        {!isLastColumn && (
          <DropdownMenuItem
            onClick={handleDeleteColumn}
            className="text-destructive focus:text-destructive"
          >
            <TrashIcon className={iconClassName} />
            Delete column
          </DropdownMenuItem>
        )}
      </>
    );

    return (
      <DropdownMenu
        open={isMenuOpen}
        onOpenChange={(open) => !open && setMenu(undefined)}
      >
        <DropdownMenuContent
          style={{
            left: menu?.bounds.x ?? 0,
            top: (menu?.bounds.y ?? 0) + (menu?.bounds.height ?? 0),
          }}
          className="fixed w-52"
        >
          <DropdownMenuItem onClick={handleCopyColumnName}>
            <CopyIcon className={iconClassName} />
            Copy column name
          </DropdownMenuItem>

          {!isLargeDataset && bulkEditItems}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  };

  return (
    <div className="relative">
      <ErrorBoundary>
        <DataEditor
          ref={dataEditorRef}
          getCellContent={getCellContent}
          columns={columns}
          gridSelection={selection}
          onGridSelectionChange={setSelection}
          rows={data.length}
          overscrollX={50} // Adds padding at the end for resizing the last column
          smoothScrollX={!isLargeDataset} // Disable smooth scrolling to improve performance
          smoothScrollY={!isLargeDataset}
          validateCell={validateCell}
          getCellsForSelection={true}
          onPaste={true}
          showSearch={showSearch}
          fillHandle={true}
          allowedFillDirections="vertical" // We can support all directions, but we need to handle datatype logic
          onKeyDown={onKeyDown}
          height={data.length > 10 ? 450 : undefined}
          width={"100%"}
          rowMarkers={{
            kind: "both",
          }}
          rowSelectionMode={"multi"}
          onCellEdited={onCellEdited}
          onColumnResize={onColumnResize}
          onHeaderMenuClick={onHeaderMenuClick}
          theme={getGlideTheme(theme)}
          trailingRowOptions={trailingRowOptions}
          onRowAppended={onRowAppend}
          maxColumnAutoWidth={600}
          maxColumnWidth={600}
        />
      </ErrorBoundary>
      {renderDropdownMenu()}

      <div className="absolute bottom-1 right-2 w-26">
        <Button
          variant="destructive"
          size="sm"
          disabled={selection.rows.length === 0}
          className="right-2 h-7"
          onClick={handleDeleteRows}
        >
          {selection.rows.length <= 1 ? "Delete row" : "Delete rows"}
        </Button>
      </div>
    </div>
  );
};

export default GlideDataEditor;
