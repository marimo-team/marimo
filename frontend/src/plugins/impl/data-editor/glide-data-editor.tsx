/* Copyright 2024 Marimo. All rights reserved. */

import DataEditor, {
  CompactSelection,
  type EditableGridCell,
  type GridCell,
  GridCellKind,
  type GridColumn,
  GridColumnIcon,
  type GridKeyEventArgs,
  type GridSelection,
  type Item,
  type Rectangle,
} from "@glideapps/glide-data-grid";
import { useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { inferFieldTypes } from "@/components/data-table/columns";
import {
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";
import { useTheme } from "@/theme/useTheme";
import { logNever } from "@/utils/assertNever";

// CSS is required for default editor styles
import "@glideapps/glide-data-grid/dist/index.css";
import { CopyIcon } from "lucide-react";
import { copyShortcutPressed } from "@/components/editor/controls/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import type { Setter } from "@/plugins/types";
import { copyToClipboard } from "@/utils/copy";
import { getGlideTheme } from "./themes";
import type { Edits, GridColumnWithKind } from "./types";
import { copyCells, getColumnWidth } from "./utils";

interface GlideDataEditorProps<T> {
  data: T[];
  fieldTypes?: FieldTypesWithExternalType | null;
  rows: number;
  onEdits: Setter<Edits>;
  host: HTMLElement;
}

export const GlideDataEditor = <T,>({
  data,
  fieldTypes,
  rows,
  onEdits,
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

  const columns: GridColumnWithKind[] = useMemo(() => {
    const columns: GridColumnWithKind[] = [];
    for (const [columnName, fieldType] of Object.entries(columnFields)) {
      columns.push({
        title: columnName,
        width:
          columnWidths[columnName] ??
          getColumnWidth(fieldType, data, columnName),
        icon: getColumnHeaderIcon(fieldType),
        kind: getColumnKind(fieldType),
        hasMenu: true,
      });
    }
    return columns;
  }, [columnFields, data, columnWidths]);

  const indexes = Object.keys(columnFields);

  const getCellContent = useEvent((cell: Item): GridCell => {
    const [col, row] = cell;
    const dataRow = data[row];

    const dataItem = dataRow[indexes[col] as keyof T];
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
  });

  const onCellEdited = useEvent((cell: Item, newValue: EditableGridCell) => {
    const [col, row] = cell;
    const key = indexes[col];

    // Mutate the data in place is demonstrated in the docs
    // eslint-disable-next-line react-hooks/react-compiler
    data[row][key as keyof T] = newValue.data as T[keyof T];

    onEdits((v) => ({
      ...v,
      edits: [...v.edits, { rowIdx: row, columnId: key, value: newValue.data }],
    }));
  });

  const onColumnResize = useEvent((column: GridColumn, newSize: number) => {
    setColumnWidths((prev) => ({
      ...prev,
      [column.title]: newSize,
    }));
  });

  const validateCell = useEvent(
    (cell: Item, newValue: EditableGridCell, _prevValue: GridCell): boolean => {
      const [col, _row] = cell;
      const key = indexes[col];

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
  );

  const onKeyDown = useEvent((e: GridKeyEventArgs) => {
    if (copyShortcutPressed(e as unknown as React.KeyboardEvent<HTMLElement>)) {
      copyCells(selection, getCellContent);
      return;
    }
  });

  const onHeaderMenuClick = useEvent((col: number, bounds: Rectangle) => {
    setMenu({ col, bounds });
  });

  const handleCopyColumnName = useEvent(async () => {
    if (menu) {
      const columnName = indexes[menu.col];
      await copyToClipboard(columnName);
      setMenu(undefined);
    }
  });

  // const handleDeleteColumn = useEvent(() => {
  //   if (!menu) {
  //     return;
  //   }

  //   const columnName = indexes[menu.col];

  //   // Create edits to clear all values in this column
  //   const deleteEdits = data.map((_, rowIdx) => ({
  //     rowIdx,
  //     columnId: columnName,
  //     value: null,
  //   }));

  //   // Add the delete edits to the existing edits
  //   onEdits((v) => ({
  //     ...v,
  //     edits: [...v.edits, ...deleteEdits],
  //   }));

  //   setMenu(undefined);
  // });

  // const handleAddColumn = useEvent((direction: "left" | "right") => {
  //   if (!menu) {
  //     return;
  //   }

  //   const currentColumnName = indexes[menu.col];
  //   const newColumnName = `Column_${Date.now()}`;

  //   // Determine the position for the new column
  //   const currentIndex = indexes.indexOf(currentColumnName);
  //   const newIndex = direction === "left" ? currentIndex : currentIndex + 1;

  //   // Create edits to add default values for the new column
  //   const addEdits = data.map((_, rowIdx) => ({
  //     rowIdx,
  //     columnId: newColumnName,
  //     value: "", // Default empty string value
  //   }));

  //   // Add the new column edits to the existing edits
  //   onEdits((v) => ({
  //     ...v,
  //     edits: [...v.edits, ...addEdits],
  //   }));

  //   setMenu(undefined);
  // });

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
            {/* 
            <DropdownMenuSeparator />

            <DropdownMenuItem onClick={() => handleAddColumn("left")}>
              <PlusIcon className={iconClassName} />
              Add column to the left
            </DropdownMenuItem>

            <DropdownMenuItem onClick={() => handleAddColumn("right")}>
              <PlusIcon className={iconClassName} />
              Add column to the right
            </DropdownMenuItem>

            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleDeleteColumn}
              className="text-destructive"
            >
              <TrashIcon className={iconClassName} />
              Delete column
            </DropdownMenuItem> */}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </>
  );
};

function getColumnKind(fieldType: DataType): GridCellKind {
  switch (fieldType) {
    case "string":
      return GridCellKind.Text;
    case "number":
      return GridCellKind.Number;
    case "boolean":
      return GridCellKind.Boolean;
    default:
      return GridCellKind.Text;
  }
}

function getColumnHeaderIcon(fieldType: DataType): GridColumnIcon {
  switch (fieldType) {
    case "string":
      return GridColumnIcon.HeaderString;
    case "number":
    case "integer":
      return GridColumnIcon.HeaderNumber;
    case "boolean":
      return GridColumnIcon.HeaderBoolean;
    case "date":
    case "datetime":
      return GridColumnIcon.HeaderDate;
    case "time":
      return GridColumnIcon.HeaderTime;
    case "unknown":
      return GridColumnIcon.HeaderString;
    default:
      logNever(fieldType);
      return GridColumnIcon.HeaderString;
  }
}

export default GlideDataEditor;
