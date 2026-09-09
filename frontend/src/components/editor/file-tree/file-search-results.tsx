/* Copyright 2026 Marimo. All rights reserved. */

import { FileIcon, FolderIcon } from "lucide-react";
import type { RefObject } from "react";
import { Tree, type NodeRendererProps, type TreeApi } from "react-arborist";
import { Spinner } from "@/components/icons/spinner";
import { cn } from "@/utils/cn";
import { useTreeDndManager } from "./dnd-wrapper";
import { FileTreeRow } from "./file-tree-row";
import type { FileTreeNode } from "./requesting-tree";
import type { useFileSearch } from "./use-file-search";

export function FileSearchResults({
  treeRef,
  search,
  height,
  onReveal,
}: {
  treeRef: RefObject<TreeApi<FileTreeNode> | null>;
  search: ReturnType<typeof useFileSearch>;
  height: number;
  onReveal: (node: FileTreeNode) => Promise<void>;
}) {
  const dndManager = useTreeDndManager();
  const { state, refetch } = search;
  if (state.status === "idle") {
    return null;
  }

  if (state.status === "error") {
    return (
      <div role="alert" className="px-3 py-2 text-sm">
        Could not search files.{" "}
        <button type="button" className="underline" onClick={refetch}>
          Retry
        </button>
      </div>
    );
  }
  if (state.status === "loading") {
    return (
      <div
        role="status"
        className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground"
      >
        <Spinner size="small" />
        Searching files…
      </div>
    );
  }
  const { files, hasMore } = state;
  const count = files.length;
  return (
    <div
      onKeyDownCapture={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          event.stopPropagation();
          treeRef.current?.focusedNode?.activate();
        }
      }}
    >
      <p role="status" className="px-3 py-2 text-xs text-muted-foreground">
        {files.length
          ? `${count} ${count === 1 ? "match" : "matches"}`
          : "No matching files or folders."}
        {hasMore && " · Refine your search for more results."}
      </p>
      <Tree<FileTreeNode>
        ref={treeRef}
        data={files}
        childrenAccessor={() => null}
        width="100%"
        height={Math.max(0, height - 48)}
        rowHeight={48}
        overscanCount={8}
        dndManager={dndManager}
        disableDrag={true}
        disableDrop={true}
        disableEdit={true}
        disableMultiSelection={true}
        selectionFollowsFocus={true}
        rowClassName="outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
        renderRow={FileTreeRow}
        onActivate={(node) => {
          void onReveal(node.data);
        }}
      >
        {SearchResult}
      </Tree>
      <p className="px-3 text-xs text-muted-foreground">
        Enter or double-click to open · Esc to clear
      </p>
    </div>
  );
}

function SearchResult({ node }: NodeRendererProps<FileTreeNode>) {
  const Icon = node.data.isDirectory ? FolderIcon : FileIcon;
  return (
    <div
      className={cn(
        "flex h-full items-start gap-2.5 px-3 py-1 cursor-pointer hover:bg-accent/50",
        node.isSelected && "bg-accent/60",
      )}
      onClick={(event) => {
        event.stopPropagation();
        node.select();
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        node.activate();
      }}
      title={node.data.path}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="truncate text-sm leading-5">{node.data.name}</div>
        <div className="truncate text-xs leading-4 text-muted-foreground">
          {node.data.path}
        </div>
      </div>
    </div>
  );
}
