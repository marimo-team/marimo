/* Copyright 2024 Marimo. All rights reserved. */

import DataEditor, {
  CompactSelection,
  type EditableGridCell,
  type GridCell,
  GridCellKind,
  type GridColumn,
  type GridKeyEventArgs,
  type GridSelection,
  type Item,
  type Rectangle,
} from "@glideapps/glide-data-grid";
import { CopyIcon } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { inferFieldTypes } from "@/components/data-table/columns";
import {
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "@/components/data-table/types";
import { copyShortcutPressed } from "@/components/editor/controls/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/theme/useTheme";
import { copyToClipboard } from "@/utils/copy";
import { getGlideTheme } from "./themes";
import type { Edits, ModifiedGridColumn } from "./types";
import {
  copyCells,
  getColumnHeaderIcon,
  getColumnKind,
  getColumnWidth,
} from "./utils";
import "@glideapps/glide-data-grid/dist/index.css"; // TODO: We are reimporting this
import { logNever } from "@/utils/assertNever";

interface GlideDataEditorProps<T> {
  data: T[];
  fieldTypes?: FieldTypesWithExternalType | null;
  rows: number;
  onAddEdits: (edits: Edits["edits"]) => void;
  onAddRows: (newRows: object[]) => void;
  host: HTMLElement;
}

export const GlideDataEditor = <T,>({
  data,
  fieldTypes,
  rows,
  onAddEdits,
  onAddRows,
  host,
}: GlideDataEditorProps<T>) => {
  const { theme } = useTheme();

  const [menu, setMenu] = useState<{ col: number; bounds: Rectangle }>();
  const [selection, setSelection] = useState<GridSelection>({
    columns: CompactSelection.empty(),
    rows: CompactSelection.empty(),
  });

  const columnFields = toFieldTypes(fieldTypes ?? inferFieldTypes(data));
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [totalRows, setTotalRows] = useState<number>(rows);

  const columns: ModifiedGridColumn[] = useMemo(() => {
    const columns: ModifiedGridColumn[] = [];
    for (const [columnName, fieldType] of Object.entries(columnFields)) {
      columns.push({
        title: columnName,
        width:
          columnWidths[columnName] ??
          getColumnWidth(fieldType, data, columnName),
        icon: getColumnHeaderIcon(fieldType),
        kind: getColumnKind(fieldType),
        dataType: fieldType,
        hasMenu: true,
      });
    }

    return columns;
  }, [columnFields, columnWidths, data]);

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

  const onKeyDown = useEvent((e: GridKeyEventArgs) => {
    // Manual copy as the default copy function is not working
    if (copyShortcutPressed(e as unknown as React.KeyboardEvent<HTMLElement>)) {
      copyCells(selection, getCellContent);
      return;
    }
  });

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

    setTotalRows(totalRows + 1);
  }, [columns, data, onAddRows, totalRows]);

  const onHeaderMenuClick = useEvent((col: number, bounds: Rectangle) => {
    setMenu({ col, bounds });
  });

  const handleCopyColumnName = useEvent(async () => {
    if (menu) {
      const columnName = columns[menu.col].title;
      await copyToClipboard(columnName);
      setMenu(undefined);
    }
  });

  const memoizedThemeValues = useMemo(() => getGlideTheme(theme), [theme]);
  const experimental = useMemo(
    () => ({
      eventTarget: (host.shadowRoot as unknown as HTMLElement) || window,
    }),
    [host],
  );

  // There is a guarantee that only one column's menu is open (as interaction is disabled outside of the menu)
  const isMenuOpen = menu !== undefined;
  const iconClassName = "mr-2 h-3.5 w-3.5";

  const memoizedTrailingRowOptions = useMemo(
    () => ({
      hint: "New row",
      sticky: true,
      tint: true,
    }),
    [],
  );

  return (
    <>
      <DataEditor
        getCellContent={getCellContent}
        columns={columns}
        rows={rows}
        smoothScrollX={true}
        smoothScrollY={true}
        validateCell={validateCell}
        // getCellsForSelection={true} // Enables copy, TODO: Not working
        onPaste={true} // Enables paste, TODO: Not working
        onKeyDown={onKeyDown}
        width="100%"
        onCellEdited={onCellEdited}
        gridSelection={selection}
        onGridSelectionChange={setSelection}
        onColumnResize={onColumnResize}
        onHeaderMenuClick={onHeaderMenuClick}
        theme={memoizedThemeValues}
        trailingRowOptions={memoizedTrailingRowOptions}
        onRowAppended={onRowAppend}
        experimental={experimental}
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
            className="fixed w-48 z-[1000]"
          >
            <DropdownMenuItem onClick={handleCopyColumnName}>
              <CopyIcon className={iconClassName} />
              Copy column name
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </>
  );
};

export default GlideDataEditor;
