/* Copyright 2026 Marimo. All rights reserved. */

import { CommandList } from "cmdk";
import {
  ChevronRightIcon,
  DownloadIcon,
  FolderIcon,
  HardDriveIcon,
  LoaderCircle,
  XIcon,
} from "lucide-react";
import React, { useCallback, useState } from "react";
import { useLocale } from "react-aria";
import { PanelEmptyState } from "@/components/editor/chrome/panels/empty-state";
import { Command, CommandInput, CommandItem } from "@/components/ui/command";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import {
  DownloadStorage,
  ListStorageEntries,
} from "@/core/storage/request-registry";
import { useStorage, useStorageActions } from "@/core/storage/state";
import type {
  StorageEntry,
  StorageNamespace,
  StoragePathKey,
} from "@/core/storage/types";
import { DEFAULT_FETCH_LIMIT, storagePathKey } from "@/core/storage/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { cn } from "@/utils/cn";
import { downloadByURL } from "@/utils/download";
import { formatBytes } from "@/utils/formatting";
import { Logger } from "@/utils/Logger";
import { Button } from "../ui/button";
import { renderFileIcon, renderProtocolIcon } from "./components";

// Pixels per depth level. Applied as paddingLeft on each full-width item
// so the selection highlight still spans the entire panel.
const INDENT_PX = 16;

function indentStyle(depth: number): React.CSSProperties {
  return { paddingLeft: depth * INDENT_PX };
}

function formatDate(timestamp: number, locale: string): string {
  const date = new Date(timestamp * 1000);
  return date.toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Extract display name from a full path (e.g., "folder/subfolder/" -> "subfolder") */
function displayName(path: string): string {
  // Remove trailing slash
  const trimmed = path.endsWith("/") ? path.slice(0, -1) : path;
  const parts = trimmed.split("/");
  return parts[parts.length - 1] || trimmed;
}

/**
 * Recursively check whether an entry (or any of its loaded descendants)
 * matches the search query.
 */
function entryMatchesSearch(
  entry: StorageEntry,
  namespace: string,
  searchValue: string,
  entriesByPath: ReadonlyMap<StoragePathKey, StorageEntry[]>,
): boolean {
  const query = searchValue.toLowerCase();

  if (displayName(entry.path).toLowerCase().includes(query)) {
    return true;
  }

  // For directories, check loaded children recursively
  if (entry.kind === "directory") {
    const children = entriesByPath.get(storagePathKey(namespace, entry.path));
    if (children) {
      return children.some((child) =>
        entryMatchesSearch(child, namespace, searchValue, entriesByPath),
      );
    }
  }

  return false;
}

/**
 * Filter entries to those matching the search (or having loaded descendants
 * that match). Returns all entries when there is no active search.
 */
function filterEntries(
  entries: StorageEntry[],
  namespace: string,
  searchValue: string,
  entriesByPath: ReadonlyMap<StoragePathKey, StorageEntry[]>,
): StorageEntry[] {
  if (!searchValue.trim()) {
    return entries;
  }
  return entries.filter((entry) =>
    entryMatchesSearch(entry, namespace, searchValue, entriesByPath),
  );
}

/**
 * Lazily loaded children of a directory entry.
 * Caches fetched entries in the Jotai store so re-expanding doesn't re-fetch.
 */
const StorageEntryChildren: React.FC<{
  namespace: string;
  prefix: string;
  depth: number;
  locale: string;
  searchValue: string;
}> = ({ namespace, prefix, depth, locale, searchValue }) => {
  const { entriesByPath } = useStorage();
  const { setEntries } = useStorageActions();
  const pathKey = storagePathKey(namespace, prefix);
  const cached = entriesByPath.get(pathKey);

  const { isPending, error } = useAsyncData(async () => {
    if (cached) {
      return;
    }
    const result = await ListStorageEntries.request({
      namespace,
      prefix,
      limit: DEFAULT_FETCH_LIMIT,
    });
    setEntries({ namespace, prefix, entries: result.entries });
  }, [namespace, prefix, !!cached]);

  const children = cached;

  if (isPending && !children) {
    return (
      <div
        className="flex items-center gap-1.5 py-1 text-xs text-muted-foreground"
        style={indentStyle(depth)}
      >
        <LoaderCircle className="h-3 w-3 animate-spin" />
        Loading...
      </div>
    );
  }

  if (error && !children) {
    return (
      <div className="py-1 text-xs text-destructive" style={indentStyle(depth)}>
        Failed to load: {error.message}
      </div>
    );
  }

  if (!children || children.length === 0) {
    return (
      <div
        className="py-1 text-xs text-muted-foreground italic"
        style={indentStyle(depth)}
      >
        Empty
      </div>
    );
  }

  const filtered = filterEntries(
    children,
    namespace,
    searchValue,
    entriesByPath,
  );

  return (
    <>
      {filtered.map((child) => (
        <StorageEntryRow
          key={child.path}
          entry={child}
          namespace={namespace}
          depth={depth}
          locale={locale}
          searchValue={searchValue}
        />
      ))}
    </>
  );
};

const StorageEntryRow: React.FC<{
  entry: StorageEntry;
  namespace: string;
  depth: number;
  locale: string;
  searchValue: string;
}> = ({ entry, namespace, depth, locale, searchValue }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { entriesByPath } = useStorage();
  const isDir = entry.kind === "directory";
  const name = displayName(entry.path);
  const hasSearch = !!searchValue.trim();

  // During a search, auto-expand directories whose loaded descendants match
  const hasMatchingDescendants =
    isDir &&
    hasSearch &&
    !!entriesByPath
      .get(storagePathKey(namespace, entry.path))
      ?.some((child) =>
        entryMatchesSearch(child, namespace, searchValue, entriesByPath),
      );

  // Folder is shown expanded by manual toggle OR by search auto-expand
  const effectiveExpanded = isExpanded || hasMatchingDescendants;

  const handleDownload = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        const result = await DownloadStorage.request({
          namespace,
          path: entry.path,
        });
        if (result.error) {
          toast({
            title: "Download failed",
            description: result.error,
            variant: "danger",
          });
          return;
        }
        if (result.url) {
          downloadByURL(result.url, result.filename ?? "download");
        }
      } catch (error) {
        Logger.error("Failed to download storage entry", error);
        toast({
          title: "Download failed",
          description: String(error),
          variant: "danger",
        });
      }
    },
    [namespace, entry.path],
  );

  return (
    <>
      <CommandItem
        className={cn(
          "text-xs flex items-center gap-1.5 cursor-pointer rounded-none group h-6.5",
          isDir && "font-medium",
        )}
        style={indentStyle(depth)}
        value={`${namespace}:${entry.path}`}
        onSelect={() => {
          if (isDir) {
            setIsExpanded(!effectiveExpanded);
          }
        }}
      >
        {isDir ? (
          <ChevronRightIcon
            className={cn(
              "h-3 w-3 shrink-0 transition-transform",
              effectiveExpanded && "rotate-90",
            )}
          />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {isDir ? (
          <FolderIcon className="h-3.5 w-3.5 text-amber-500 shrink-0" />
        ) : (
          renderFileIcon(name)
        )}
        <span className="truncate flex-1 text-left">{name}</span>
        {!isDir && (
          <Tooltip content="Download">
            <Button
              variant="ghost"
              size="icon"
              className="opacity-0 group-hover:opacity-100 transition-opacity hover:shadow-none"
              onClick={handleDownload}
            >
              <DownloadIcon className="h-3 w-3 text-muted-foreground" />
            </Button>
          </Tooltip>
        )}
        {entry.size > 0 && (
          <span className="text-[10px] text-muted-foreground pr-2 opacity-0 group-hover:opacity-100 transition-opacity tabular-nums">
            {formatBytes(entry.size, locale)}
          </span>
        )}
        {entry.lastModified != null && (
          <Tooltip
            content={`Last modified: ${new Date(entry.lastModified * 1000).toLocaleString()}`}
          >
            <span className="text-[10px] text-muted-foreground pr-2 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
              {formatDate(entry.lastModified, locale)}
            </span>
          </Tooltip>
        )}
      </CommandItem>
      {isDir && effectiveExpanded && (
        <StorageEntryChildren
          namespace={namespace}
          prefix={entry.path}
          depth={depth + 1}
          locale={locale}
          searchValue={searchValue}
        />
      )}
    </>
  );
};

const StorageNamespaceSection: React.FC<{
  namespace: StorageNamespace;
  locale: string;
  searchValue: string;
}> = ({ namespace, locale, searchValue }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const { entriesByPath } = useStorage();
  const namespaceName = namespace.name ?? namespace.displayName;

  const {
    data: fetchedEntries,
    isPending,
    error,
  } = useAsyncData(async () => {
    const result = await ListStorageEntries.request({
      namespace: namespaceName,
      prefix: "",
      limit: DEFAULT_FETCH_LIMIT,
    });
    return result.entries;
  }, [namespaceName]);

  // Fetched entries take priority, fall back to initial namespace entries
  const entries = fetchedEntries ?? namespace.storageEntries;
  const filtered = filterEntries(
    entries,
    namespaceName,
    searchValue,
    entriesByPath,
  );

  return (
    <>
      <CommandItem
        value={namespace.name}
        onSelect={() => setIsExpanded(!isExpanded)}
        className="flex flex-row font-semibold h-7 text-xs gap-1.5 bg-(--slate-2) text-muted-foreground"
      >
        <ChevronRightIcon
          className={cn(
            "h-3 w-3 shrink-0 transition-transform",
            isExpanded && "rotate-90",
          )}
        />
        {renderProtocolIcon(namespace.protocol)}
        <span>{namespace.displayName}</span>
        <span className="text-[10px] text-muted-foreground font-normal tabular-nums ml-auto">
          {namespace.protocol}://
        </span>
      </CommandItem>
      {isExpanded && (
        <>
          {isPending && entries.length === 0 && (
            <div
              className="flex items-center gap-1.5 py-1 text-xs text-muted-foreground"
              style={indentStyle(1)}
            >
              <LoaderCircle className="h-3 w-3 animate-spin" />
              Loading...
            </div>
          )}
          {error && entries.length === 0 && (
            <div
              className="py-1 text-xs text-destructive"
              style={indentStyle(1)}
            >
              Failed to load entries: {error.message}
            </div>
          )}
          {!isPending && entries.length === 0 && !error && (
            <div
              className="py-1 text-xs text-muted-foreground italic"
              style={indentStyle(1)}
            >
              No entries
            </div>
          )}
          {searchValue && filtered.length === 0 && entries.length > 0 && (
            <div
              className="py-1 text-xs text-muted-foreground italic"
              style={indentStyle(1)}
            >
              No matches
            </div>
          )}
          {filtered.map((entry) => (
            <StorageEntryRow
              key={entry.path}
              entry={entry}
              namespace={namespaceName}
              depth={1}
              locale={locale}
              searchValue={searchValue}
            />
          ))}
        </>
      )}
    </>
  );
};

export const StorageInspector: React.FC = () => {
  const { namespaces } = useStorage();
  const { locale } = useLocale();
  const [searchValue, setSearchValue] = useState("");
  const hasSearch = !!searchValue.trim();

  if (namespaces.length === 0) {
    return (
      <PanelEmptyState
        title="No storage connected"
        description="Create an Obstore or Fsspec connection in your notebook"
        icon={<HardDriveIcon className="h-8 w-8" />}
      />
    );
  }

  return (
    <Command
      className="border-b bg-background rounded-none h-full pb-10 overflow-auto outline-hidden"
      shouldFilter={false}
    >
      <div className="flex items-center w-full border-b">
        <CommandInput
          placeholder="Search files..."
          className="h-6 m-1"
          value={searchValue}
          onValueChange={setSearchValue}
          rootClassName="flex-1 border-b-0"
        />
        {hasSearch && (
          <Button
            variant="text"
            size="xs"
            className="float-right border-none px-2 m-0 h-full"
            onClick={() => setSearchValue("")}
          >
            <XIcon className="h-4 w-4" />
          </Button>
        )}
      </div>
      <CommandList className="flex flex-col">
        {namespaces.map((ns) => (
          <StorageNamespaceSection
            key={ns.name ?? ns.displayName}
            namespace={ns}
            locale={locale}
            searchValue={searchValue}
          />
        ))}
      </CommandList>
    </Command>
  );
};
