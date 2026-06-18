/* Copyright 2026 Marimo. All rights reserved. */

import { CommandList } from "cmdk";
import {
  CopyIcon,
  DownloadIcon,
  FolderIcon,
  HardDriveIcon,
  HelpCircleIcon,
  LoaderCircle,
  PlusIcon,
  ViewIcon,
  XIcon,
} from "lucide-react";
import React, { useCallback, useState } from "react";
import { useLocale } from "react-aria";
import { EngineVariable } from "@/components/databases/engine-variable";
import { useAddCodeToNewCell } from "@/components/editor/cell/useAddCell";
import { PanelEmptyState } from "@/components/editor/chrome/panels/empty-state";
import { AddConnectionDialog } from "@/components/editor/connections/add-connection-dialog";
import {
  FILE_ICON_COLOR,
  renderFileIcon,
} from "@/components/editor/file-tree/file-icons";
import {
  MENU_ITEM_ICON_CLASS,
  MoreActionsButton,
  RefreshIconButton,
  TreeChevron,
} from "@/components/editor/file-tree/tree-actions";
import { Command, CommandInput, CommandItem } from "@/components/ui/command";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { DownloadStorage } from "@/core/storage/request-registry";
import {
  useStorage,
  useStorageActions,
  useStorageEntries,
  useStoragePageFetcher,
} from "@/core/storage/state";
import type {
  StorageEntry,
  StorageNamespace,
  StoragePageMetadata,
  StoragePathKey,
} from "@/core/storage/types";
import { storagePathKey } from "@/core/storage/types";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { downloadByURL } from "@/utils/download";
import { formatBytes } from "@/utils/formatting";
import { Logger } from "@/utils/Logger";
import { ErrorState } from "../datasources/components";
import { Button } from "../ui/button";
import { ProtocolIcon } from "./components";
import { StorageFileViewer } from "./storage-file-viewer";
import { STORAGE_SNIPPETS } from "./storage-snippets";

interface OpenFileInfo {
  entry: StorageEntry;
  namespace: string;
  protocol: string;
  backendType: StorageNamespace["backendType"];
}

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

function directoryPrefix(path: string): string {
  return path.endsWith("/") ? path : `${path}/`;
}

/**
 * Stable, unique identity for an entry row. Prefer the
 * backend's stable id when present and fall back to the list index
 */
export function storageEntryKey(entry: StorageEntry, index: number): string {
  const id = entry.metadata?.id;
  if (typeof id === "string" && id.length > 0) {
    return id;
  }
  return `${entry.path}::${index}`;
}

interface SearchContext {
  namespace: string;
  searchValue: string;
  entriesByPath: ReadonlyMap<StoragePathKey, StorageEntry[]>;
}

/**
 * Recursively check whether an entry (or any of its loaded descendants)
 * matches the search query.
 */
function entryMatchesSearch(
  entry: StorageEntry,
  { namespace, searchValue, entriesByPath }: SearchContext,
): boolean {
  const query = searchValue.trim().toLowerCase();
  const path = entry.path.toLowerCase();
  const name = displayName(entry.path).toLowerCase();

  if (name.includes(query) || path.includes(query)) {
    return true;
  }

  // For directories, check loaded children recursively
  if (entry.kind === "directory") {
    const children = entriesByPath.get(
      storagePathKey(namespace, directoryPrefix(entry.path)),
    );
    if (children) {
      return children.some((child) =>
        entryMatchesSearch(child, { namespace, searchValue, entriesByPath }),
      );
    }
  }

  return false;
}

/**
 * Filter entries to those matching the search (or having loaded descendants
 * that match). Returns all entries when there is no active search.
 */
export function filterEntries(
  entries: StorageEntry[],
  context: SearchContext,
): StorageEntry[] {
  if (!context.searchValue.trim()) {
    return entries;
  }
  return entries.filter((entry) => entryMatchesSearch(entry, context));
}

const MAX_REMOTE_SEARCH_PAGES = 5;

type RemoteSearchState =
  | { query: string; status: "idle" }
  | { query: string; status: "searching" }
  | { query: string; status: "found" }
  | { query: string; status: "exhausted" }
  | { query: string; status: "capped" }
  | { query: string; status: "error"; error: Error };

type RemoteSearchByNamespace = Record<string, RemoteSearchState>;

function idleRemoteSearch(query: string): RemoteSearchState {
  return { query, status: "idle" };
}

function canRetryRemoteSearch(remoteSearch: RemoteSearchState): boolean {
  return (
    remoteSearch.status === "idle" ||
    remoteSearch.status === "error" ||
    remoteSearch.status === "capped"
  );
}

/**
 * Whether the backend may still have an unfetched page for a prefix: either we
 * have never listed it, or its last listing returned a next-page token.
 */
function hasUnfetchedPrefixPage(
  searchKey: StoragePathKey,
  entriesByPath: ReadonlyMap<StoragePathKey, StorageEntry[]>,
  pageMetadataByPath: ReadonlyMap<StoragePathKey, StoragePageMetadata>,
): boolean {
  return (
    entriesByPath.get(searchKey) === undefined ||
    pageMetadataByPath.get(searchKey)?.nextPageToken != null
  );
}

function canSearchMoreRemoteEntries({
  hasSearch,
  hasLoadedMatches,
  isPending,
  remoteSearch,
  searchKey,
  entriesByPath,
  pageMetadataByPath,
}: {
  hasSearch: boolean;
  hasLoadedMatches: boolean;
  isPending: boolean;
  remoteSearch: RemoteSearchState;
  searchKey: StoragePathKey;
  entriesByPath: ReadonlyMap<StoragePathKey, StorageEntry[]>;
  pageMetadataByPath: ReadonlyMap<StoragePathKey, StoragePageMetadata>;
}): boolean {
  if (!hasSearch || hasLoadedMatches || isPending) {
    return false;
  }
  if (!canRetryRemoteSearch(remoteSearch)) {
    return false;
  }

  return hasUnfetchedPrefixPage(searchKey, entriesByPath, pageMetadataByPath);
}

/**
 * Returns the directory prefix to query the backend with for a given search.
 *
 * Object stores like obstore evaluate prefixes on a path-segment basis
 * (`folder/x` would only match `folder/x/...`, never `folder/xsomething`), so
 * for substring searches we list the parent directory and filter on the
 * client. Returns `""` when the search has no directory component.
 */
export function remoteSearchPrefix(searchValue: string): string {
  const trimmed = searchValue.trim();
  const lastSlash = trimmed.lastIndexOf("/");
  return lastSlash === -1 ? "" : trimmed.slice(0, lastSlash + 1);
}

/**
 * Shallow check (no recursion into loaded children) used inside the
 * remote-search pagination loop to decide whether a fetched page has
 * any candidates worth surfacing to the user.
 */
function entryMatchesQueryShallow(
  entry: StorageEntry,
  searchValue: string,
): boolean {
  const query = searchValue.trim().toLowerCase();
  if (!query) {
    return true;
  }
  return (
    entry.path.toLowerCase().includes(query) ||
    displayName(entry.path).toLowerCase().includes(query)
  );
}

const LoadMoreStorageEntries: React.FC<{
  depth: number;
  isLoading: boolean;
  error?: Error;
  onLoadMore: () => void;
}> = ({ depth, isLoading, error, onLoadMore }) => {
  return (
    <div className="py-px text-xs" style={indentStyle(depth)}>
      <Button
        variant="text"
        size="xs"
        className="h-6 px-0 hover:text-blue-600"
        disabled={isLoading}
        onClick={onLoadMore}
      >
        {isLoading && <LoaderCircle className="h-3 w-3 mr-1 animate-spin" />}
        {isLoading ? "Loading..." : "Load more"}
      </Button>
      {error && (
        <span className="ml-2 text-destructive">
          Failed to load: {error.message}
        </span>
      )}
    </div>
  );
};

/**
 * Lazily loaded children of a directory entry.
 * Caches fetched entries in the Jotai store so re-expanding doesn't re-fetch.
 */
const StorageEntryChildren: React.FC<{
  namespace: string;
  protocol: string;
  rootPath: string;
  backendType: StorageNamespace["backendType"];
  prefix: string;
  depth: number;
  locale: string;
  searchValue: string;
  onOpenFile: (info: OpenFileInfo) => void;
}> = ({
  namespace,
  protocol,
  rootPath,
  backendType,
  prefix,
  depth,
  locale,
  searchValue,
  onOpenFile,
}) => {
  const { entriesByPath } = useStorage();
  const {
    entries: children,
    isPending,
    error,
    hasMore,
    loadMore,
    isLoadingMore,
    loadMoreError,
  } = useStorageEntries(namespace, prefix);

  if (isPending) {
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

  if (error) {
    return (
      <div className="py-1 text-xs text-destructive" style={indentStyle(depth)}>
        Failed to load: {error.message}
      </div>
    );
  }

  if (children.length === 0) {
    return (
      <div
        className="py-1 text-xs text-muted-foreground italic"
        style={indentStyle(depth)}
      >
        Empty
      </div>
    );
  }

  const filtered = filterEntries(children, {
    namespace,
    searchValue,
    entriesByPath,
  });

  return (
    <>
      {filtered.map((child) => {
        const rowKey = storageEntryKey(child, children.indexOf(child));
        return (
          <StorageEntryRow
            key={rowKey}
            rowKey={rowKey}
            entry={child}
            namespace={namespace}
            protocol={protocol}
            rootPath={rootPath}
            backendType={backendType}
            depth={depth}
            locale={locale}
            searchValue={searchValue}
            onOpenFile={onOpenFile}
          />
        );
      })}
      {hasMore && (
        <LoadMoreStorageEntries
          depth={depth}
          isLoading={isLoadingMore}
          error={loadMoreError}
          onLoadMore={loadMore}
        />
      )}
    </>
  );
};

const StorageEntryRow: React.FC<{
  entry: StorageEntry;
  rowKey: string;
  namespace: string;
  protocol: string;
  rootPath: string;
  backendType: StorageNamespace["backendType"];
  depth: number;
  locale: string;
  searchValue: string;
  onOpenFile: (info: OpenFileInfo) => void;
}> = ({
  entry,
  rowKey,
  namespace,
  protocol,
  rootPath,
  backendType,
  depth,
  locale,
  searchValue,
  onOpenFile,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { entriesByPath } = useStorage();
  const addCodeToNewCell = useAddCodeToNewCell();
  const isDir = entry.kind === "directory";
  const name = displayName(entry.path);
  const hasSearch = !!searchValue.trim();

  const selfMatches =
    isDir &&
    hasSearch &&
    name.toLowerCase().includes(searchValue.trim().toLowerCase());

  // During a search, auto-expand directories whose loaded descendants match
  const hasMatchingDescendants =
    isDir &&
    hasSearch &&
    !!entriesByPath
      .get(storagePathKey(namespace, directoryPrefix(entry.path)))
      ?.some((child) =>
        entryMatchesSearch(child, { namespace, searchValue, entriesByPath }),
      );

  // Folder is shown expanded by manual toggle OR by search auto-expand
  const effectiveExpanded = isExpanded || hasMatchingDescendants;

  const handleDownload = useCallback(async () => {
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
  }, [namespace, entry.path]);

  return (
    <>
      <CommandItem
        className={cn(
          "text-xs flex items-center gap-1.5 cursor-pointer rounded-none group h-6.5",
          isDir && "font-medium",
        )}
        style={indentStyle(depth)}
        value={`${namespace}:${rowKey}`}
        onSelect={() => {
          if (isDir) {
            setIsExpanded(!effectiveExpanded);
          } else {
            onOpenFile({ entry, namespace, protocol, backendType });
          }
        }}
      >
        {isDir ? (
          <TreeChevron isExpanded={effectiveExpanded} className="h-3 w-3" />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {isDir ? (
          <FolderIcon
            className={cn("h-3.5 w-3.5 shrink-0", FILE_ICON_COLOR.directory)}
          />
        ) : (
          renderFileIcon(name)
        )}
        <span className="truncate flex-1 text-left">{name}</span>
        <div className="flex items-center">
          {entry.size > 0 && (
            <span className="text-[10px] text-muted-foreground pr-2 opacity-0 group-hover:opacity-100 transition-opacity tabular-nums">
              {formatBytes(entry.size, locale)}
            </span>
          )}
          {entry.lastModified != null && (
            <Tooltip
              content={`Last modified: ${new Date(entry.lastModified * 1000).toLocaleString()}`}
            >
              <span className="text-[10px] text-muted-foreground pr-1 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                {formatDate(entry.lastModified, locale)}
              </span>
            </Tooltip>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild={true}>
              <MoreActionsButton
                iconClassName="h-3 w-3"
                onClick={(e) => e.stopPropagation()}
              />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              onClick={(e) => e.stopPropagation()}
              onCloseAutoFocus={(e) => e.preventDefault()}
            >
              {!isDir && (
                <DropdownMenuItem
                  onSelect={() =>
                    onOpenFile({ entry, namespace, protocol, backendType })
                  }
                >
                  <ViewIcon className={MENU_ITEM_ICON_CLASS} />
                  View
                </DropdownMenuItem>
              )}
              <DropdownMenuItem
                onSelect={async () => {
                  await copyToClipboard(entry.path);
                  toast({ title: "Copied to clipboard" });
                }}
              >
                <CopyIcon className={MENU_ITEM_ICON_CLASS} />
                Copy path
              </DropdownMenuItem>
              {!isDir && (
                <DropdownMenuItem onSelect={() => handleDownload()}>
                  <DownloadIcon className={MENU_ITEM_ICON_CLASS} />
                  Download
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              {STORAGE_SNIPPETS.map((snippet) => {
                const code = snippet.getCode({
                  variableName: namespace,
                  protocol,
                  entry,
                  backendType,
                });
                if (code === null) {
                  return null;
                }
                const Icon = snippet.icon;
                return (
                  <DropdownMenuItem
                    key={snippet.id}
                    onSelect={() => addCodeToNewCell(code)}
                  >
                    <Icon className={MENU_ITEM_ICON_CLASS} />
                    {snippet.label}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CommandItem>
      {isDir && effectiveExpanded && (
        <StorageEntryChildren
          namespace={namespace}
          protocol={protocol}
          rootPath={rootPath}
          backendType={backendType}
          prefix={directoryPrefix(entry.path)}
          depth={depth + 1}
          locale={locale}
          searchValue={selfMatches ? "" : searchValue} // When a parent directory matches the search, we don't need to filter the children.
          onOpenFile={onOpenFile}
        />
      )}
    </>
  );
};

const StorageNamespaceSection: React.FC<{
  namespace: StorageNamespace;
  locale: string;
  searchValue: string;
  remoteSearch: RemoteSearchState;
  onContinueRemoteSearch: () => void;
  onOpenFile: (info: OpenFileInfo) => void;
}> = ({
  namespace,
  locale,
  searchValue,
  remoteSearch,
  onContinueRemoteSearch,
  onOpenFile,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const { entriesByPath, pageMetadataByPath } = useStorage();
  const { clearNamespaceCache } = useStorageActions();
  const namespaceName = namespace.name ?? namespace.displayName;

  const {
    entries: fetchedEntries,
    isPending,
    error,
    hasMore,
    loadMore,
    isLoadingMore,
    loadMoreError,
    refetch,
  } = useStorageEntries(namespaceName);

  const handleRefresh = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      clearNamespaceCache(namespaceName);
      refetch();
    },
    [namespaceName, clearNamespaceCache, refetch],
  );

  // While loading, fall back to initial entries from the namespace notification
  const entries = isPending ? namespace.storageEntries : fetchedEntries;
  const filtered = filterEntries(entries, {
    namespace: namespaceName,
    searchValue,
    entriesByPath,
  });
  const searchPrefix = remoteSearchPrefix(searchValue);
  const searchKey = storagePathKey(namespaceName, searchPrefix);
  const remoteEntries =
    searchPrefix === "" ? [] : (entriesByPath.get(searchKey) ?? []);
  // The fetched page is the whole parent directory; we still need to filter
  // it by the full search query before showing entries to the user.
  const filteredRemoteEntries = filterEntries(remoteEntries, {
    namespace: namespaceName,
    searchValue,
    entriesByPath,
  });
  const hasSearch = !!searchValue.trim();
  const hasLoadedMatches =
    filtered.length > 0 || filteredRemoteEntries.length > 0;
  const canSearchMore =
    searchPrefix !== "" &&
    canSearchMoreRemoteEntries({
      hasSearch,
      hasLoadedMatches,
      isPending,
      remoteSearch,
      searchKey,
      entriesByPath,
      pageMetadataByPath,
    });

  const showRemoteResults = hasSearch && filtered.length === 0;
  const statusRow = (() => {
    if (isPending && entries.length === 0) {
      return (
        <span className="flex items-center gap-1.5">
          <LoaderCircle className="h-3 w-3 animate-spin" />
          Loading...
        </span>
      );
    }
    if (remoteSearch.status === "searching") {
      return (
        <span className="flex items-center gap-1.5">
          <LoaderCircle className="h-3 w-3 animate-spin" />
          Searching more entries...
        </span>
      );
    }
    if (remoteSearch.status === "error") {
      return (
        <span className="text-destructive">
          Search failed: {remoteSearch.error.message}
        </span>
      );
    }
    if (remoteSearch.status === "capped") {
      return (
        <span className="flex items-center gap-1.5">
          Searched more entries.
          <Button
            variant="text"
            size="xs"
            className="h-5 px-0 text-xs hover:text-blue-600"
            onClick={onContinueRemoteSearch}
          >
            Continue searching
          </Button>
          <span className="text-[10px]">(or press Enter)</span>
        </span>
      );
    }
    if (remoteSearch.status === "exhausted" && !hasLoadedMatches) {
      return "No matches";
    }
    if (!hasSearch && !isPending && entries.length === 0) {
      return "No entries";
    }
    if (canSearchMore) {
      return (
        <span className="flex items-center gap-1.5">
          No loaded matches.
          <Button
            variant="text"
            size="xs"
            className="h-5 px-0 text-xs hover:text-blue-600"
            onClick={onContinueRemoteSearch}
          >
            Search more entries
          </Button>
          <span className="text-[10px]">(or press Enter)</span>
        </span>
      );
    }
    if (hasSearch && !hasLoadedMatches && entries.length > 0) {
      return "No matches";
    }
    return null;
  })();

  return (
    <>
      <CommandItem
        value={namespace.name}
        onSelect={() => setIsExpanded(!isExpanded)}
        className="flex flex-row font-semibold h-7 text-xs gap-1.5 bg-(--slate-2) text-muted-foreground rounded-none"
      >
        <TreeChevron isExpanded={isExpanded} className="h-3 w-3" />
        <ProtocolIcon protocol={namespace.protocol} />
        <span>{namespace.displayName}</span>
        {namespace.name && (
          <span className="text-xs text-muted-foreground font-normal">
            (<EngineVariable variableName={namespace.name} />)
          </span>
        )}
        <RefreshIconButton
          onClick={handleRefresh}
          tooltip="Refresh storage connection"
          className="p-0"
          iconClassName="h-3 w-3"
        />
        <span className="text-[10px] text-muted-foreground font-normal tabular-nums ml-auto">
          {namespace.rootPath || "(root)"}
        </span>
      </CommandItem>
      {isExpanded && (
        <>
          {error && entries.length === 0 && (
            <ErrorState
              error={error}
              style={indentStyle(1)}
              className="py-1 text-xs h-auto overflow-auto max-h-32 items-start"
              showIcon={false}
            />
          )}
          {!error && statusRow && (
            <div
              className="py-1 text-xs text-muted-foreground italic"
              style={indentStyle(1)}
            >
              {statusRow}
            </div>
          )}
          {filtered.map((entry) => {
            const rowKey = storageEntryKey(entry, entries.indexOf(entry));
            return (
              <StorageEntryRow
                key={rowKey}
                rowKey={rowKey}
                entry={entry}
                namespace={namespaceName}
                protocol={namespace.protocol}
                rootPath={namespace.rootPath}
                backendType={namespace.backendType}
                depth={1}
                locale={locale}
                searchValue={searchValue}
                onOpenFile={onOpenFile}
              />
            );
          })}
          {showRemoteResults &&
            filteredRemoteEntries.map((entry) => {
              const rowKey = storageEntryKey(
                entry,
                remoteEntries.indexOf(entry),
              );
              return (
                <StorageEntryRow
                  key={`remote-search:${rowKey}`}
                  rowKey={`remote-search:${rowKey}`}
                  entry={entry}
                  namespace={namespaceName}
                  protocol={namespace.protocol}
                  rootPath={namespace.rootPath}
                  backendType={namespace.backendType}
                  depth={1}
                  locale={locale}
                  searchValue={searchValue}
                  onOpenFile={onOpenFile}
                />
              );
            })}
          {hasMore && !canSearchMore && (
            <LoadMoreStorageEntries
              depth={1}
              isLoading={isLoadingMore}
              error={loadMoreError}
              onLoadMore={loadMore}
            />
          )}
        </>
      )}
    </>
  );
};

export const StorageInspector: React.FC = () => {
  const { namespaces, entriesByPath, pageMetadataByPath } = useStorage();
  const { locale } = useLocale();
  const [searchValue, setSearchValue] = useState("");
  const [remoteSearchByNamespace, setRemoteSearchByNamespace] =
    useState<RemoteSearchByNamespace>({});
  const [openFile, setOpenFile] = useState<OpenFileInfo | null>(null);
  const fetchStoragePage = useStoragePageFetcher();
  const hasSearch = !!searchValue.trim();
  const currentQuery = searchValue.trim();

  const remoteSearchForNamespace = useCallback(
    (namespaceName: string): RemoteSearchState => {
      const remoteSearch = remoteSearchByNamespace[namespaceName];
      if (remoteSearch?.query === currentQuery) {
        return remoteSearch;
      }
      return idleRemoteSearch(currentQuery);
    },
    [currentQuery, remoteSearchByNamespace],
  );

  const setRemoteSearch = useCallback(
    (namespaceName: string, remoteSearch: RemoteSearchState) => {
      setRemoteSearchByNamespace((state) => ({
        ...state,
        [namespaceName]: remoteSearch,
      }));
    },
    [],
  );

  const canContinueRemoteSearch = useCallback(
    (namespace: StorageNamespace): boolean => {
      if (!currentQuery) {
        return false;
      }

      const namespaceName = namespace.name ?? namespace.displayName;
      const searchPrefix = remoteSearchPrefix(currentQuery);
      // No directory component in the query - the user is doing a fuzzy
      // search and the backend can't help; rely on local filtering instead.
      if (searchPrefix === "") {
        return false;
      }

      const remoteSearch = remoteSearchForNamespace(namespaceName);
      if (!canRetryRemoteSearch(remoteSearch)) {
        return false;
      }

      // Already surfacing matches from loaded entries?
      const rootEntries =
        entriesByPath.get(storagePathKey(namespaceName, "")) ??
        namespace.storageEntries;
      const rootMatches = filterEntries(rootEntries, {
        namespace: namespaceName,
        searchValue: currentQuery,
        entriesByPath,
      });
      if (rootMatches.length > 0) {
        return false;
      }

      const searchKey = storagePathKey(namespaceName, searchPrefix);
      const prefixEntries = entriesByPath.get(searchKey) ?? [];
      const prefixMatches = filterEntries(prefixEntries, {
        namespace: namespaceName,
        searchValue: currentQuery,
        entriesByPath,
      });
      if (prefixMatches.length > 0) {
        return false;
      }

      return hasUnfetchedPrefixPage(
        searchKey,
        entriesByPath,
        pageMetadataByPath,
      );
    },
    [currentQuery, entriesByPath, pageMetadataByPath, remoteSearchForNamespace],
  );

  const continueRemoteSearch = useCallback(
    async (namespace: StorageNamespace) => {
      if (!canContinueRemoteSearch(namespace)) {
        return;
      }

      const query = currentQuery;
      const namespaceName = namespace.name ?? namespace.displayName;
      const prefix = remoteSearchPrefix(query);
      const key = storagePathKey(namespaceName, prefix);
      const cachedEntries = entriesByPath.get(key);
      let nextPageToken = pageMetadataByPath.get(key)?.nextPageToken ?? null;
      let hasFetchedAny = cachedEntries !== undefined;

      setRemoteSearch(namespaceName, { query, status: "searching" });
      try {
        for (let page = 0; page < MAX_REMOTE_SEARCH_PAGES; page++) {
          // First iteration with a stale cache hit needs no fetch; just check
          // the cached page before paginating.
          const shouldFetch = !hasFetchedAny || nextPageToken !== null;
          let newEntries: StorageEntry[] = [];
          if (shouldFetch) {
            const result = await fetchStoragePage({
              namespace: namespaceName,
              prefix,
              pageToken: nextPageToken,
              append: hasFetchedAny,
            });
            newEntries = result.entries;
            nextPageToken = result.next_page_token ?? null;
            hasFetchedAny = true;
          }

          const entriesToCheck = shouldFetch
            ? newEntries
            : (cachedEntries ?? []);
          const hasMatches = entriesToCheck.some((entry) =>
            entryMatchesQueryShallow(entry, query),
          );
          if (hasMatches) {
            setRemoteSearch(namespaceName, { query, status: "found" });
            return;
          }

          if (nextPageToken === null) {
            setRemoteSearch(namespaceName, { query, status: "exhausted" });
            return;
          }
        }
        setRemoteSearch(namespaceName, { query, status: "capped" });
      } catch (error) {
        setRemoteSearch(namespaceName, {
          query,
          status: "error",
          error: error instanceof Error ? error : new Error(String(error)),
        });
      }
    },
    [
      canContinueRemoteSearch,
      currentQuery,
      entriesByPath,
      fetchStoragePage,
      pageMetadataByPath,
      setRemoteSearch,
    ],
  );

  const continueRemoteSearches = useCallback(() => {
    const searchableNamespaces = namespaces.filter(canContinueRemoteSearch);
    for (const namespace of searchableNamespaces) {
      void continueRemoteSearch(namespace);
    }
  }, [canContinueRemoteSearch, continueRemoteSearch, namespaces]);

  if (namespaces.length === 0) {
    return (
      <PanelEmptyState
        title="No storage connected"
        description={
          <span>
            Create an obstore or fsspec connection in your notebook. See the{" "}
            <a
              className="text-link"
              href="https://docs.marimo.io/guides/working_with_data/remote_storage/#quick-start"
              target="_blank"
              rel="noopener noreferrer"
            >
              docs
            </a>
            .
          </span>
        }
        action={
          <AddConnectionDialog defaultTab="storage">
            <Button variant="outline" size="sm">
              Add remote storage
              <PlusIcon className="h-4 w-4 ml-2" />
            </Button>
          </AddConnectionDialog>
        }
        icon={<HardDriveIcon className="h-8 w-8" />}
      />
    );
  }

  return (
    <div className="h-full flex flex-col">
      {openFile && (
        <StorageFileViewer
          entry={openFile.entry}
          namespace={openFile.namespace}
          protocol={openFile.protocol}
          backendType={openFile.backendType}
          onBack={() => setOpenFile(null)}
        />
      )}
      <Command
        className={cn(
          "border-b bg-background rounded-none h-full pb-10 overflow-auto outline-hidden scrollbar-thin",
          // We want to keep the command open but hidden when a file is opened to preserve state (folders opened etc.)
          // TODO: Preserve scroll position
          openFile && "hidden",
        )}
        shouldFilter={false}
      >
        <div className="flex items-center w-full border-b">
          <CommandInput
            placeholder="Search entries..."
            className="h-6 m-1"
            value={searchValue}
            onValueChange={setSearchValue}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                namespaces.some(canContinueRemoteSearch)
              ) {
                event.preventDefault();
                continueRemoteSearches();
              }
            }}
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
          <Tooltip
            content="Search by file name within loaded entries, or by prefix (e.g. 'folder/x') for backend search. Press Enter to fetch more results."
            delayDuration={200}
          >
            <HelpCircleIcon className="h-3.5 w-3.5 shrink-0 cursor-help text-muted-foreground hover:text-foreground mr-2" />
          </Tooltip>
          <AddConnectionDialog defaultTab="storage">
            <Button
              variant="ghost"
              size="sm"
              className="px-2 border-0 border-l border-muted-background rounded-none focus-visible:ring-0 focus-visible:ring-offset-0"
            >
              <PlusIcon className="h-4 w-4" />
            </Button>
          </AddConnectionDialog>
        </div>
        <CommandList className="flex flex-col">
          {namespaces.map((ns) => {
            const namespaceName = ns.name ?? ns.displayName;
            return (
              <StorageNamespaceSection
                key={namespaceName}
                namespace={ns}
                locale={locale}
                searchValue={searchValue}
                remoteSearch={remoteSearchForNamespace(namespaceName)}
                onContinueRemoteSearch={() => void continueRemoteSearch(ns)}
                onOpenFile={setOpenFile}
              />
            );
          })}
        </CommandList>
      </Command>
    </div>
  );
};
