/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column } from "@tanstack/react-table";
import { ChevronDownIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { Sets } from "@/utils/sets";
import { smartMatch } from "@/utils/smartMatch";
import { Spinner } from "../icons/spinner";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "../ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { SentinelCell } from "./sentinel-cell";
import { detectSentinel, stringifyUnknownValue } from "./utils";

const TOP_K_ROWS = 30;

interface Props<TData, TValue> {
  column: Column<TData, TValue>;
  calculateTopKRows?: CalculateTopKRows;
  chosenValues: unknown[];
  onChange: (values: unknown[]) => void;
}

export const FilterByValuesPicker = <TData, TValue>({
  column,
  calculateTopKRows,
  chosenValues,
  onChange,
}: Props<TData, TValue>) => {
  const [open, setOpen] = useState(false);

  const chosenValuesSet = useMemo(() => new Set(chosenValues), [chosenValues]);

  const selectedValuesStr = useMemo(() => {
    if (chosenValuesSet.size === 0) {
      return "Select values…";
    }
    const items = [...chosenValuesSet].map((v) =>
      stringifyUnknownValue({ value: v }),
    );
    return `[${items.join(", ")}]`;
  }, [chosenValuesSet]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild={true}>
        <Button
          variant="outline"
          size="xs"
          className="h-6 mb-1 w-full justify-between font-normal"
        >
          <span
            className={cn(
              "truncate",
              chosenValuesSet.size === 0 && "text-muted-foreground",
            )}
          >
            {selectedValuesStr}
          </span>
          <ChevronDownIcon className="h-4 w-4 opacity-50 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0">
        <FilterByValuesList
          column={column}
          calculateTopKRows={calculateTopKRows}
          chosenValues={chosenValuesSet}
          onChange={onChange}
        />
      </PopoverContent>
    </Popover>
  );
};

interface FilterByValuesListProps<TData, TValue> {
  column: Column<TData, TValue>;
  calculateTopKRows?: CalculateTopKRows;
  chosenValues: Set<unknown>;
  onChange: (values: unknown[]) => void;
}

/**
 * Search + checkbox list that powers the "filter by values" picker.
 */
export const FilterByValuesList = <TData, TValue>({
  column,
  calculateTopKRows,
  chosenValues,
  onChange,
}: FilterByValuesListProps<TData, TValue>) => {
  const [query, setQuery] = useState<string>("");

  const { data, isPending, error } = useAsyncData(async () => {
    if (!calculateTopKRows) {
      return null;
    }
    const res = await calculateTopKRows({ column: column.id, k: TOP_K_ROWS });
    return res.data;
  }, [calculateTopKRows, column.id]);

  const filteredData = useMemo(() => {
    if (!data) {
      return [];
    }
    try {
      // try to do includes and also smart match for prefixes
      return data.filter(([value, _count]) => {
        if (value === undefined) {
          return false;
        }
        const str = String(value);
        return (
          smartMatch(query, str) ||
          str.toLowerCase().includes(query.toLowerCase())
        );
      });
    } catch (error_) {
      Logger.error("Error filtering data", error_);
      return [];
    }
  }, [data, query]);

  const handleToggle = (value: unknown) => {
    onChange([...Sets.toggle(chosenValues, value)]);
  };

  const allVisibleChecked =
    filteredData.length > 0 &&
    filteredData.every(([value]) => chosenValues.has(value));

  const selectAllState: boolean | "indeterminate" = allVisibleChecked
    ? true
    : chosenValues.size > 0
      ? "indeterminate"
      : false;

  const handleToggleAll = () => {
    if (!data) {
      return;
    }
    const next = new Set(chosenValues);
    if (allVisibleChecked) {
      for (const [value] of filteredData) {
        next.delete(value);
      }
    } else {
      for (const [value] of filteredData) {
        next.add(value);
      }
    }
    onChange([...next]);
  };

  if (isPending) {
    return <Spinner size="medium" className="mx-auto mt-12 mb-10" />;
  }

  if (error) {
    return <ErrorBanner error={error} className="my-10 mx-4" />;
  }

  if (!data) {
    return (
      <div className="py-6 px-4 text-sm text-muted-foreground text-center">
        No values available
      </div>
    );
  }

  return (
    <Command className="text-sm outline-hidden" shouldFilter={false}>
      <CommandInput
        placeholder={`Search among the top ${data.length} values`}
        autoFocus={true}
        onValueChange={(value) => setQuery(value.trim())}
      />
      <CommandEmpty>No results found.</CommandEmpty>
      <CommandList>
        {filteredData.length > 0 && (
          <CommandItem
            value="__select-all__"
            className="border-b rounded-none px-3"
            onSelect={handleToggleAll}
          >
            <Checkbox
              checked={selectAllState}
              aria-label="Select all"
              className="mr-3 h-3.5 w-3.5"
            />
            <span className="font-bold flex-1">{column.id}</span>
            <span className="font-bold">Count</span>
          </CommandItem>
        )}
        {filteredData.map(([value, count]) => {
          const isSelected = chosenValues.has(value);
          const valueString = stringifyUnknownValue({ value });
          const sentinel = detectSentinel(
            value,
            column.columnDef.meta?.dataType,
          );
          return (
            <CommandItem
              key={valueString}
              value={valueString}
              className="not-last:border-b rounded-none px-3"
              onSelect={() => handleToggle(value)}
            >
              <Checkbox
                checked={isSelected}
                aria-label="Select row"
                className="mr-3 h-3.5 w-3.5"
              />
              <span className="flex-1 overflow-hidden max-h-20 line-clamp-3">
                {sentinel ? <SentinelCell sentinel={sentinel} /> : valueString}
              </span>
              <span className="ml-3">{count}</span>
            </CommandItem>
          );
        })}
      </CommandList>
      {data.length === TOP_K_ROWS && (
        <span className="text-xs text-muted-foreground py-1.5 text-center">
          Only showing the top {TOP_K_ROWS} values
        </span>
      )}
    </Command>
  );
};
