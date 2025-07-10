/* Copyright 2024 Marimo. All rights reserved. */

import DataEditor, {
  type DataEditorRef,
  type EditableGridCell,
  type GridCell,
  GridCellKind,
  type GridColumn,
  type GridKeyEventArgs,
  type Item,
  type Rectangle,
} from "@glideapps/glide-data-grid";
import { CopyIcon, PlusIcon, TrashIcon } from "lucide-react";
import React, { useCallback, useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { inferFieldTypes } from "@/components/data-table/columns";
import {
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "@/components/data-table/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/theme/useTheme";
import { copyToClipboard } from "@/utils/copy";
import { getGlideTheme } from "./themes";
import { BulkEdit, type Edits, type ModifiedGridColumn } from "./types";
import {
  getColumnHeaderIcon,
  getColumnKind,
  isPositionalEdit,
  isRowEdit,
  pasteCells,
} from "./utils";
import "@glideapps/glide-data-grid/dist/index.css"; // TODO: We are reimporting this
import {
  copyShortcutPressed,
  isModifierKey,
  pasteShortcutPressed,
} from "@/components/editor/controls/utils";
import { Button } from "@/components/ui/button";
import { useOnMount } from "@/hooks/useLifecycle";
import { useNonce } from "@/hooks/useNonce";
import { logNever } from "@/utils/assertNever";

interface GlideDataEditorProps<T> {
  data: T[];
  fieldTypes?: FieldTypesWithExternalType | null;
  edits: Edits["edits"];
  onAddEdits: (edits: Edits["edits"]) => void;
  onAddRows: (newRows: object[]) => void;
  onDeleteRows: (rows: number[]) => void;
}

export const GlideDataEditor = <T,>({
  data,
  fieldTypes,
  edits,
  onAddEdits,
  onAddRows,
  onDeleteRows,
}: GlideDataEditorProps<T>) => {
  const { theme } = useTheme();

  const dataEditorRef = useRef<DataEditorRef>(null);

  const [menu, setMenu] = useState<{ col: number; bounds: Rectangle }>();
  const [showSearch, setShowSearch] = useState<boolean>(false);
  const [selection, setSelection] = React.useState<GridSelection>({
    columns: CompactSelection.empty(),
    rows: CompactSelection.empty(),
  });

  const columnFields = toFieldTypes(fieldTypes ?? inferFieldTypes(data));
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
          // This is an existing row, update the data directly
          // @ts-expect-error: Mutate data directly for performance
          // eslint-disable-next-line react-hooks/react-compiler
          data[edit.rowIdx][edit.columnId] = edit.value;
        }
      } else if (isRowEdit(edit) && edit.type === BulkEdit.Remove) {
        // Add rows is currently handled under positional edits, so we only cover deletes here
        data.splice(edit.rowIdx, 1);
      }
    }

    // Add new rows in order
    const sortedNewRows = [...newRows.entries()]
      .sort(([a], [b]) => a - b)
      .map(([, row]) => row);

    if (sortedNewRows.length > 0) {
      data.push(...(sortedNewRows as T[]));
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

      // Mutate the data in place is demonstrated in the docs
      // eslint-disable-next-line react-hooks/react-compiler
      data[row][key as keyof T] = newData as T[keyof T];

      onAddEdits([{ rowIdx: row, columnId: key, value: newData }]);
    },
    [columns, data, onAddEdits],
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

  // Hack to emit copy and paste events as these events aren't triggered automatically in shadow DOM
  // TODO: Paste does not work
  const onKeyDown = useCallback(
    (e: GridKeyEventArgs) => {
      if (dataEditorRef.current) {
        const keyboardEvent = e as unknown as React.KeyboardEvent<HTMLElement>;

        if (copyShortcutPressed(keyboardEvent)) {
          dataEditorRef.current.emit("copy");
        } else if (pasteShortcutPressed(keyboardEvent)) {
          pasteCells({
            selection,
            data,
            columns,
            onAddEdits,
          });
        } else if (isModifierKey(keyboardEvent) && keyboardEvent.key === "f") {
          setShowSearch((prev) => !prev);
          e.stopPropagation();
          e.preventDefault();
        } else if (keyboardEvent.key === "Escape") {
          setShowSearch(false);
        }
      }
    },
    [selection, data, onAddEdits, columns],
  );

  const onRowAppend = useCallback(() => {
    const newRow = Object.fromEntries(
      columns.map((column) => {
        const dataType = column.dataType;
        switch (dataType) {
          case "boolean":
            return [column.title, false];
          case "number":
          case "integer":
            return [column.title, 0];
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
    data.push(newRow);
  }, [columns, data, onAddRows]);

  const handleDeleteRows = () => {
    const rows = selection.rows.toArray();
    onDeleteRows(rows);

    let index = 0;
    for (const row of rows) {
      const adjustedRow = row - index; // Adjust for previously deleted rows
      data.splice(adjustedRow, 1);
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

  // There is a guarantee that only one column's menu is open (as interaction is disabled outside of the menu)
  const isMenuOpen = menu !== undefined;
  const iconClassName = "mr-2 h-3.5 w-3.5";

  const trailingRowOptions = {
    hint: "New row",
    sticky: true,
    tint: true,
  };

  // For large datasets, we disable smooth scrolling to improve performance
  const smoothScrolling = !(data.length > 100_000);

  return (
    <>
      <DataEditor
        ref={dataEditorRef}
        getCellContent={getCellContent}
        columns={columns}
        rows={data.length}
        overscrollX={50} // Adds padding at the end for resizing the last column
        smoothScrollX={smoothScrolling}
        smoothScrollY={smoothScrolling}
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
          headerDisabled: true,
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
      {isMenuOpen && (
        <DropdownMenu
          open={isMenuOpen}
          onOpenChange={(open) => !open && setMenu(undefined)}
        >
          <DropdownMenuContent
            style={{
              left: menu?.bounds.x ?? 0,
              top: (menu?.bounds.y ?? 0) + (menu?.bounds.height ?? 0),
            }}
            className="fixed w-48"
          >
            <DropdownMenuItem onClick={handleCopyColumnName}>
              <CopyIcon className={iconClassName} />
              Copy column name
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem>
              <PlusIcon className={iconClassName} />
              Add column to the left
            </DropdownMenuItem>
            <DropdownMenuItem>
              <PlusIcon className={iconClassName} />
              Add column to the right
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem className="text-destructive focus:text-destructive">
              <TrashIcon className={iconClassName} />
              Delete column
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      <Button
        variant="destructive"
        size="sm"
        disabled={selection.rows.length === 0}
        className="absolute bottom-1 right-2 h-7"
        onClick={handleDeleteRows}
      >
        {selection.rows.length <= 1 ? "Delete row" : "Delete rows"}
      </Button>
    </>
  );
};

export default GlideDataEditor;
