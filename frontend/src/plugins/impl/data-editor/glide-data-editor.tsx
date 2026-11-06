/* Copyright 2026 Marimo. All rights reserved. */

import DataEditor, {
  CompactSelection,
  type DataEditorRef,
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
import {
  DropdownCell as DropdownCellRenderer,
  type DropdownCellType,
} from "@glideapps/glide-data-grid-cells";
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
  isValidCellValue,
  pasteCells,
} from "./glide-utils";
import { getGlideTheme } from "./themes";
import "@glideapps/glide-data-grid/dist/index.css"; // TODO: We are reimporting this
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import type { DataType } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import { Events } from "@/utils/events";
import { normalizeBoolean } from "./column-types";
import { AddColumnSub, RenameColumnSub } from "./components";
import { GlideDataEditorPortal } from "./glide-portal";
import {
  BulkEdit,
  type ColumnTypes,
  type EditorRow,
  type Edits,
  type ModifiedGridColumn,
} from "./types";

function getEditedValue(newValue: EditableGridCell): unknown {
  if (newValue.kind !== GridCellKind.Custom) {
    return newValue.data;
  }
  const data = newValue.data as { kind?: unknown; value?: unknown };
  return data.kind === "dropdown-cell" ? data.value : newValue.data;
}

interface GlideDataEditorProps {
  data: EditorRow[];
  columnFields: FieldTypes;
  columnTypes: ColumnTypes;
  editableColumns: string[] | "all";
  onAddEdits: (edits: Edits["edits"]) => void;
}

export const GlideDataEditor = ({
  data,
  columnFields,
  columnTypes,
  editableColumns,
  onAddEdits,
}: GlideDataEditorProps) => {
  const { theme } = useTheme();
  const dataEditorRef = useRef<DataEditorRef>(null);
  const portalElementRef = useRef<HTMLDivElement>(null);

  const [menu, setMenu] = useState<{ col: number; bounds: Rectangle }>();
  const [showSearch, setShowSearch] = useState<boolean>(false);
  const [selection, setSelection] = React.useState<GridSelection>({
    columns: CompactSelection.empty(),
    rows: CompactSelection.empty(),
  });

  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const editableColumnSet = useMemo(
    () => (editableColumns === "all" ? null : new Set(editableColumns)),
    [editableColumns],
  );

  const columns: ModifiedGridColumn[] = useMemo(() => {
    const columns: ModifiedGridColumn[] = [];
    for (const [columnName, fieldType] of columnFields) {
      const editable =
        editableColumnSet === null || editableColumnSet.has(columnName);

      columns.push({
        id: columnName,
        title: columnName,
        width: columnWidths[columnName], // Enables resizing
        icon: editable
          ? getColumnHeaderIcon(fieldType)
          : GridColumnIcon.ProtectedColumnOverlay,
        style: "normal",
        kind: getColumnKind(fieldType),
        dataType: fieldType,
        configuredType: columnTypes.get(columnName),
        hasMenu: true,
        themeOverride: editable
          ? undefined
          : {
              bgCell: theme === "light" ? "#F9F9FA" : "#1e1e21",
            },
      });
    }

    return columns;
  }, [columnFields, columnTypes, columnWidths, editableColumnSet, theme]);

  const getCellContent = useCallback(
    (cell: Item): GridCell => {
      const [col, row] = cell;
      const dataRow = data[row];

      const dataItem = dataRow[columns[col].title];
      const columnKind = columns[col].kind;
      const editable =
        editableColumnSet === null || editableColumnSet.has(columns[col].title);

      const configuredType = columns[col].configuredType;
      if (Array.isArray(configuredType)) {
        const value = typeof dataItem === "string" ? dataItem : "";
        return {
          kind: GridCellKind.Custom,
          allowOverlay: editable,
          readonly: !editable,
          copyData: value,
          data: {
            kind: "dropdown-cell",
            value,
            allowedValues: configuredType,
          },
        } satisfies DropdownCellType;
      }

      if (columnKind === GridCellKind.Boolean) {
        const value =
          columns[col].configuredType === "boolean"
            ? normalizeBoolean(dataItem, columns[col].title)
            : Boolean(dataItem);
        return {
          kind: GridCellKind.Boolean,
          allowOverlay: false,
          readonly: !editable,
          data: value,
        };
      }

      if (columnKind === GridCellKind.Number && typeof dataItem === "number") {
        return {
          kind: GridCellKind.Number,
          allowOverlay: editable,
          readonly: !editable,
          displayData: String(dataItem),
          data: dataItem,
        };
      }

      return {
        kind: GridCellKind.Text,
        allowOverlay: editable,
        readonly: !editable,
        displayData: String(dataItem),
        data: String(dataItem),
      };
    },
    [columns, data, editableColumnSet],
  );

  const onCellEdited = useCallback(
    (cell: Item, newValue: EditableGridCell) => {
      const [col, row] = cell;
      const column = columns[col];
      const key = column.title;

      // Deletes are not handled by validateCell, so we need to handle them here.
      // Custom dropdown cells carry their selected value inside their data.
      let newData = getEditedValue(newValue);
      if (Array.isArray(column.configuredType)) {
        if (
          typeof newData !== "string" ||
          !column.configuredType.includes(newData)
        ) {
          return;
        }
      } else if (column.configuredType === "boolean") {
        newData = normalizeBoolean(newData, key);
      }
      if (
        (column.dataType === "number" || column.dataType === "integer") &&
        (newValue.data === undefined || newValue.data === "")
      ) {
        newData = null;
      }

      onAddEdits([{ rowIdx: row, columnId: key, value: newData }]);
    },
    [columns, onAddEdits],
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

      const dataType = columnFields.get(key);
      const configuredType = columnTypes.get(key);
      const value = getEditedValue(newValue);
      return isValidCellValue(dataType, value, configuredType);
    },
    [columnFields, columns, columnTypes],
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
          columns,
          editableColumns,
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
    [columns, data, editableColumns, onAddEdits, selection],
  );

  const onRowAppend = useCallback(() => {
    const newRow: EditorRow = Object.fromEntries(
      columns.map((column) => {
        const dataType = column.dataType;
        if (column.configuredType === "boolean") {
          return [column.title, false];
        }
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
          case "geometry":
          case "unknown":
            return [
              column.title,
              Array.isArray(column.configuredType)
                ? column.configuredType[0]
                : "",
            ];
          default:
            logNever(dataType);
            return [column.title, ""];
        }
      }),
    );
    onAddEdits(
      Object.entries(newRow).map(([columnId, value]) => ({
        rowIdx: data.length,
        columnId,
        value,
      })),
    );
  }, [columns, data.length, onAddEdits]);

  const handleDeleteRows = () => {
    const rows = selection.rows.toArray();
    onAddEdits(
      rows.map((rowIdx, index) => ({
        rowIdx: rowIdx - index,
        type: BulkEdit.Remove,
      })),
    );

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
      // Validate the new column name
      if (columnFields.has(newName)) {
        toastColumnExists(newName);
        return;
      }

      onAddEdits([{ columnIdx: menu.col, newName, type: BulkEdit.Rename }]);
      setMenu(undefined);
    }
  };

  const handleDeleteColumn = () => {
    if (menu) {
      onAddEdits([{ columnIdx: menu.col, type: BulkEdit.Remove }]);
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
      if (columnFields.has(columnName)) {
        toastColumnExists(columnName);
        return;
      }

      onAddEdits([
        {
          columnIdx: clampedColumnIdx,
          newName: columnName,
          dataType,
          type: BulkEdit.Insert,
        },
      ]);
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

  // For now, only allow renaming and deleting if all columns are editable
  // Users who set specific columns usually will not want to rename or delete columns
  const allowRenameDelete = editableColumns === "all";

  const renderDropdownMenu = () => {
    if (!isMenuOpen) {
      return;
    }

    const bulkEditItems = (
      <>
        {allowRenameDelete && (
          <RenameColumnSub
            currentColumnName={columns[menu.col].title}
            onRename={handleRenameColumn}
            onCancel={() => setMenu(undefined)}
          />
        )}

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
        {!isLastColumn && allowRenameDelete && (
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
    <div className="relative w-full min-w-0">
      <GlideDataEditorPortal portalRef={portalElementRef} />
      <ErrorBoundary>
        <DataEditor
          ref={dataEditorRef}
          // Glide types portalElementRef as RefObject<HTMLElement> (non-null); React 19 refs include null.
          // @ts-expect-error glide-data-grid stale RefObject typing
          portalElementRef={portalElementRef}
          getCellContent={getCellContent}
          customRenderers={[DropdownCellRenderer]}
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
