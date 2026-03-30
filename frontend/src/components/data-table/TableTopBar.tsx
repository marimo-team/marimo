/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

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
import { Tooltip } from "../ui/tooltip";
import { type DownloadActionProps, DownloadAs } from "./download-actions";

interface TableTopBarProps extends Partial<DownloadActionProps> {
  enableSearch: boolean;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  reloading?: boolean;
  showChartBuilder?: boolean;
  toggleDisplayHeader?: () => void;
  showTableExplorer?: boolean;
  togglePanel?: (panelType: PanelType) => void;
  isAnyPanelOpen?: boolean;
}

export const TableTopBar: React.FC<TableTopBarProps> = ({
  enableSearch,
  searchQuery,
  onSearchQueryChange,
  reloading,
  showChartBuilder,
  toggleDisplayHeader,
  showTableExplorer,
  togglePanel,
  isAnyPanelOpen,
  downloadAs,
  downloadFileName,
}) => {
  const [isSearchExpanded, setIsSearchExpanded] = useState(false);
  const [internalValue, setInternalValue] = useState(searchQuery || "");
  const debouncedSearch = useDebounce(internalValue, 500);
  const onSearch = useEvent(
    onSearchQueryChange ??
      (() => {
        /** no-op */
      }),
  );
  const inputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    onSearch(debouncedSearch);
  }, [debouncedSearch, onSearch]);

  useEffect(() => {
    if (isSearchExpanded) {
      inputRef.current?.focus();
    } else {
      setInternalValue("");
    }
  }, [isSearchExpanded]);

  const hasAnyAction =
    (enableSearch && onSearchQueryChange) ||
    showChartBuilder ||
    showTableExplorer ||
    downloadAs;

  if (!hasAnyAction) {
    return null;
  }

  return (
    <div className="flex items-center h-10 px-2 border-b gap-1">
      {/* Left: Search */}
      {onSearchQueryChange && enableSearch && (
        <div className="flex items-center">
          <div
            className={cn(
              "flex items-center gap-1 rounded-full border px-2 transition-all duration-200 ease-in-out overflow-hidden",
              isSearchExpanded ? "w-56" : "w-8 border-transparent",
            )}
          >
            <button
              type="button"
              className="shrink-0 flex items-center justify-center"
              onClick={() => setIsSearchExpanded(!isSearchExpanded)}
            >
              <SearchIcon className="w-4 h-4 text-muted-foreground" />
            </button>
            <input
              ref={inputRef}
              type="text"
              className={cn(
                "h-6 border-none bg-transparent focus:outline-hidden text-sm transition-all duration-200",
                isSearchExpanded ? "w-full opacity-100" : "w-0 opacity-0",
              )}
              value={internalValue}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setIsSearchExpanded(false);
                }
              }}
              onChange={(e) => setInternalValue(e.target.value)}
              placeholder="Search..."
            />
            {isSearchExpanded && reloading && <Spinner size="small" />}
            {isSearchExpanded && (
              <Button
                variant="text"
                size="xs"
                className="h-5 w-5 p-0 shrink-0"
                onClick={() => setIsSearchExpanded(false)}
              >
                <XIcon className="w-3 h-3 text-muted-foreground" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Right: Actions */}
      <div className="ml-auto flex items-center gap-0.5">
        {showChartBuilder && (
          <Tooltip content="Chart builder">
            <Button
              variant="text"
              size="xs"
              className="print:hidden"
              onClick={toggleDisplayHeader}
            >
              <ChartSplineIcon className="w-4 h-4 text-muted-foreground" />
            </Button>
          </Tooltip>
        )}
        {showTableExplorer && togglePanel && (
          <Tooltip content="Toggle table explorer">
            <Button
              variant="text"
              size="xs"
              className="print:hidden"
              onClick={() => togglePanel(PANEL_TYPES.ROW_VIEWER)}
            >
              <PanelRightIcon
                className={cn(
                  "w-4 h-4 text-muted-foreground",
                  isAnyPanelOpen && "text-primary",
                )}
              />
            </Button>
          </Tooltip>
        )}
        {downloadAs && (
          <DownloadAs
            downloadAs={downloadAs}
            downloadFileName={downloadFileName}
          />
        )}
      </div>
    </div>
  );
};
