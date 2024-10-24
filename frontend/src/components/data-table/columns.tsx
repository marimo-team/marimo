/* Copyright 2024 Marimo. All rights reserved. */
import type { ColumnDef } from "@tanstack/react-table";
import {
  DataTableColumnHeader,
  DataTableColumnHeaderWithSummary,
} from "./column-header";
import { Checkbox } from "../ui/checkbox";
import { MimeCell } from "./mime-cell";
import { uniformSample } from "./uniformSample";
import type { DataType } from "@/core/kernel/messages";
import { TableColumnSummary } from "./column-summary";
import type { FilterType } from "./filters";
import type { FieldTypesWithExternalType } from "./types";
import { UrlDetector } from "./url-detector";
import { Arrays } from "@/utils/arrays";

interface ColumnInfo {
  key: string;
  type: "primitive" | "mime";
}

function getColumnInfo<T>(items: T[]): ColumnInfo[] {
  // No items
  if (items.length === 0) {
    return Arrays.EMPTY;
  }

  // Not an object
  if (typeof items[0] !== "object") {
    return Arrays.EMPTY;
  }

  const keys = new Map<string, ColumnInfo>();

  // This can be slow for large datasets,
  // so only sample 10 evenly distributed rows
  uniformSample(items, 10).forEach((item) => {
    if (typeof item !== "object") {
      return;
    }
    // We will be a bit defensive and assume values are not homogeneous.
    // If any is a mimetype, then we will treat it as a mimetype (i.e. not sortable)
    Object.entries(item as object).forEach(([key, value], idx) => {
      const currentValue = keys.get(key);
      if (!currentValue) {
        // Set for the first time
        keys.set(key, {
          key,
          type: isPrimitiveOrNullish(value) ? "primitive" : "mime",
        });
      }
      // If we have a value, and it is a primitive, we could possibly upgrade it to a mime
      if (
        currentValue &&
        currentValue.type === "primitive" &&
        !isPrimitiveOrNullish(value)
      ) {
        keys.set(key, {
          key,
          type: "mime",
        });
      }
    });
  });

  return [...keys.values()];
}

export const NAMELESS_COLUMN_PREFIX = "__m_column__";

export function generateColumns<T>({
  items,
  rowHeaders,
  selection,
  fieldTypes,
}: {
  items: T[];
  rowHeaders: string[];
  selection: "single" | "multi" | null;
  fieldTypes?: FieldTypesWithExternalType;
}): Array<ColumnDef<T>> {
  const columnInfo = getColumnInfo(items);
  const rowHeadersSet = new Set(rowHeaders);

  const columns = columnInfo.map(
    (info, idx): ColumnDef<T> => ({
      id: info.key || `${NAMELESS_COLUMN_PREFIX}${idx}`,
      // Use an accessorFn instead of an accessorKey because column names
      // may have periods in them ...
      // https://github.com/TanStack/table/issues/1671
      accessorFn: (row) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return (row as any)[info.key];
      },

      header: ({ column }) => {
        const dtype = column.columnDef.meta?.dtype;
        const headerWithType = (
          <div className="flex flex-col">
            <span className="font-bold">{info.key}</span>
            {dtype && (
              <span className="text-xs text-muted-foreground">{dtype}</span>
            )}
          </div>
        );

        // Row headers have no summaries
        if (rowHeadersSet.has(info.key)) {
          return (
            <DataTableColumnHeader header={headerWithType} column={column} />
          );
        }

        return (
          <DataTableColumnHeaderWithSummary
            header={headerWithType}
            column={column}
            summary={<TableColumnSummary columnId={info.key} />}
          />
        );
      },

      cell: ({ column, renderValue, getValue }) => {
        // Row headers are bold
        if (rowHeadersSet.has(info.key)) {
          return <b>{String(renderValue())}</b>;
        }

        const value = getValue();

        const format = column.getColumnFormatting?.();
        if (format) {
          return column.applyColumnFormatting(value);
        }

        if (isPrimitiveOrNullish(value)) {
          const rendered = renderValue();
          if (rendered == null) {
            return "";
          }
          if (typeof rendered === "string") {
            return <UrlDetector text={rendered} />;
          }
          return String(rendered);
        }
        return <MimeCell value={value} />;
      },
      // Only enable sorting for primitive types and non-row headers
      enableSorting: info.type === "primitive" && !rowHeadersSet.has(info.key),
      // Remove any default filtering
      filterFn: undefined,
      meta: {
        type: info.type,
        rowHeader: rowHeadersSet.has(info.key),
        filterType: getFilterTypeForFieldType(fieldTypes?.[info.key]?.[0]),
        dtype: fieldTypes?.[info.key]?.[1],
        dataType: fieldTypes?.[info.key]?.[0],
      },
    }),
  );

  if (selection === "single" || selection === "multi") {
    columns.unshift({
      id: "__select__",
      maxSize: 40,
      header: ({ table }) =>
        selection === "multi" ? (
          <Checkbox
            data-testid="select-all-checkbox"
            checked={table.getIsAllPageRowsSelected()}
            onCheckedChange={(value) =>
              table.toggleAllPageRowsSelected(!!value)
            }
            aria-label="Select all"
            className="mx-1.5 my-4"
          />
        ) : null,
      cell: ({ row }) => (
        <Checkbox
          data-testid="select-row-checkbox"
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
          className="mx-2"
        />
      ),
      enableSorting: false,
      enableHiding: false,
    });
  }

  return columns;
}

function isPrimitiveOrNullish(value: unknown): boolean {
  if (value == null) {
    return true;
  }
  const isObject = typeof value === "object";
  return !isObject;
}

function getFilterTypeForFieldType(
  type: DataType | undefined,
): FilterType | undefined {
  if (type === undefined) {
    return undefined;
  }
  switch (type) {
    case "string":
      return "text";
    case "number":
      return "number";
    case "integer":
      return "number";
    case "date":
      return "date";
    case "datetime":
      return "datetime";
    case "time":
      return "time";
    case "boolean":
      return "boolean";
    default:
      return undefined;
  }
}
