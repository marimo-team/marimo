/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Table } from "@tanstack/react-table";
import { useDebounce } from "@uidotdev/usehooks";
import {
  ChartSplineIcon,
  PanelRightIcon,
  SearchIcon,
  XIcon,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import useEvent from "react-use-event-hook";
import { cn } from "@/utils/cn";
import {
  PANEL_TYPES,
  type PanelType,
} from "../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { Spinner } from "../icons/spinner";
import { Button } from "../ui/button";
import { ColumnVisibilityDropdown } from "./column-visibility-dropdown";
import { type ExportActionProps, ExportMenu } from "./export-actions";

const NOOP_ON_SEARCH = () => {
  /** no-op*/
};

interface TableTopBarProps<TData> extends Partial<ExportActionProps> {
  table: Table<TData>;
  showSearch: boolean;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  reloading?: boolean;
  showChartBuilder?: boolean;
  isChartBuilderOpen?: boolean;
  toggleDisplayHeader?: () => void;
  showTableExplorer?: boolean;
  togglePanel?: (panelType: PanelType) => void;
  isAnyPanelOpen?: boolean;
  sizeBytes?: number | null;
  sizeBytesIsLoading?: boolean;
}

export const TableTopBar = <TData,>({
  table,
  showSearch,
  searchQuery,
  onSearchQueryChange,
  reloading,
  showChartBuilder,
  isChartBuilderOpen,
  toggleDisplayHeader,
  showTableExplorer,
  togglePanel,
  isAnyPanelOpen,
  downloadAs,
  sizeBytes,
  sizeBytesIsLoading,
}: TableTopBarProps<TData>) => {
  const [internalValue, setInternalValue] = useState(searchQuery || "");
  const debouncedSearch = useDebounce(internalValue, 500);
  const onSearch = useEvent(onSearchQueryChange ?? NOOP_ON_SEARCH);
  const inputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    onSearch(debouncedSearch);
  }, [debouncedSearch, onSearch]);

  return (
    <div className="flex items-center h-10 px-2 border-b gap-2">
      {onSearchQueryChange && showSearch && (
        <div className="flex flex-1 items-center gap-1 px-2 rounded-sm focus-within:ring-1 focus-within:ring-border transition-shadow">
          <SearchIcon className="w-4 h-4 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            className="h-6 border-none bg-transparent focus:outline-hidden text-sm w-full min-w-0"
            value={internalValue}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setInternalValue("");
                inputRef.current?.blur();
              }
            }}
            onChange={(e) => setInternalValue(e.target.value)}
            placeholder="Search..."
          />
          {reloading && <Spinner size="small" />}
          {internalValue && (
            <Button
              variant="text"
              size="xs"
              className="h-5 w-5 p-0 shrink-0"
              onClick={() => setInternalValue("")}
            >
              <XIcon className="w-3 h-3 text-muted-foreground" />
            </Button>
          )}
        </div>
      )}

      <div className="flex items-center shrink-0 ml-auto">
        <ColumnVisibilityDropdown table={table} />
        {showChartBuilder && (
          <Button
            variant="text"
            size="xs"
            className={cn(
              "print:hidden text-xs gap-1",
              isChartBuilderOpen ? "text-primary" : "text-muted-foreground",
            )}
            onClick={toggleDisplayHeader}
          >
            <ChartSplineIcon className="w-3.5 h-3.5" />
            Visualize
          </Button>
        )}
        {showTableExplorer && togglePanel && (
          <Button
            variant="text"
            size="xs"
            className={cn(
              "print:hidden text-xs gap-1",
              isAnyPanelOpen ? "text-primary" : "text-muted-foreground",
            )}
            onClick={() => togglePanel(PANEL_TYPES.ROW_VIEWER)}
          >
            <PanelRightIcon className="w-3.5 h-3.5" />
            Explore
          </Button>
        )}
        {downloadAs && (
          <ExportMenu
            downloadAs={downloadAs}
            sizeBytes={sizeBytes}
            sizeBytesIsLoading={sizeBytesIsLoading}
          />
        )}
      </div>
    </div>
  );
};
