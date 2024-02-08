/* Copyright 2024 Marimo. All rights reserved. */
import { ColumnDef } from "@tanstack/react-table";
import { DataTableColumnHeader } from "./column-header";
import { Checkbox } from "../ui/checkbox";
import { MimeCell } from "./mime-cell";

interface ColumnInfo {
  key: string;
  type: "primitive" | "mime";
}

export function getColumnInfo<T>(items: T[]): ColumnInfo[] {
  // No items
  if (items.length === 0) {
    return [];
  }

  // Not an object
  if (typeof items[0] !== "object") {
    return [];
  }

  const keys = new Map<string, ColumnInfo>();
  items.forEach((item) => {
    if (typeof item !== "object") {
      return;
    }
    // We will be a bit defensive and assume values are not homogeneous.
    // If any is a mimetype, then we will treat it as a mimetype (i.e. not sortable)
    Object.entries(item as object).forEach(([key, value]) => {
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

export function generateColumns<T>(
  items: T[],
  rowHeaders: Array<ColumnDef<T>>,
  selection: "single" | "multi" | null,
): Array<ColumnDef<T>> {
  const columnInfo = getColumnInfo(items);
  const columns = columnInfo.map(
    (info): ColumnDef<T> => ({
      id: info.key,
      // Use an accessorFn instead of an accessorKey because column names
      // may have periods in them ...
      // https://github.com/TanStack/table/issues/1671
      accessorFn: (row) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return (row as any)[info.key];
      },
      header: ({ column }) => {
        return <DataTableColumnHeader header={info.key} column={column} />;
      },
      cell: ({ renderValue, getValue }) => {
        const value = getValue();
        if (isPrimitiveOrNullish(value)) {
          return renderValue();
        }
        return <MimeCell value={value} />;
      },
      enableSorting: info.type === "primitive",
    }),
  );

  if (rowHeaders.length > 0) {
    columns.unshift(...rowHeaders);
  }

  if (selection === "single" || selection === "multi") {
    columns.unshift({
      id: "select",
      header: ({ table }) =>
        selection === "multi" ? (
          <Checkbox
            checked={table.getIsAllPageRowsSelected()}
            onCheckedChange={(value) =>
              table.toggleAllPageRowsSelected(!!value)
            }
            aria-label="Select all"
            className="mx-2"
          />
        ) : null,
      cell: ({ row }) => (
        <Checkbox
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

/**
 * Turn rowHeaders into a list of columns
 */
export function generateIndexColumns<T>(
  rowHeaders: Array<[string, string[]]>,
): Array<ColumnDef<T>> {
  return rowHeaders.map(
    ([title, keys], idx): ColumnDef<T> => ({
      id: `_row_header_${idx}`,
      accessorFn: (_row, idx) => {
        return keys[idx];
      },
      header: ({ column }) => {
        return <DataTableColumnHeader header={title} column={column} />;
      },
      cell: ({ renderValue }) => {
        return <b>{String(renderValue())}</b>;
      },
      enableSorting: false,
    }),
  );
}

function isPrimitiveOrNullish(value: unknown): boolean {
  if (value == null) {
    return true;
  }
  return typeof value !== "object";
}
