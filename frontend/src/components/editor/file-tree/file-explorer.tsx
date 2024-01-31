/* Copyright 2024 Marimo. All rights reserved. */
import { NodeApi, NodeRendererProps, Tree, SimpleTree } from "react-arborist";

import React, { useMemo, useState } from "react";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FileIcon,
  FolderIcon,
} from "lucide-react";
import { useOnMount } from "@/hooks/useLifecycle";
import { sendListFiles } from "@/core/network/requests";
import { FileInfo } from "@/core/network/types";

export const FileExplorer: React.FC<{
  height: number;
}> = ({ height }) => {
  const [data, setData] = useState<FileInfo[]>([]);
  const tree = useMemo(() => new SimpleTree<FileInfo>(data), [data]);

  useOnMount(() => {
    if (data.length > 0) {
      return;
    }
    // Fetch initial data on mount
    sendListFiles({ path: undefined }).then((data) => {
      setData(data.files);
    });
  });

  return (
    <Tree<FileInfo>
      width="100%"
      height={height}
      className="h-full"
      data={tree.data}
      openByDefault={false}
      onToggle={(id) => {
        const node = tree.find(id);
        if (!node) {
          return;
        }
        if (!node.data.isDirectory) {
          return;
        }

        // We may attempt to load empty directories multiple times
        // but that is fine
        if (node.children && node.children.length > 0) {
          // Already loaded
          return;
        }

        sendListFiles({ path: id }).then((data) => {
          tree.update({ id, changes: { children: data.files } });
          setData(tree.data);
        });
      }}
      padding={15}
      rowHeight={30}
      indent={INDENT_STEP}
      overscanCount={1000}
      // Not implemented yet
      disableMultiSelection={true}
      // disableDrag={true}
      disableDrop={true}
      disableEdit={true}
    >
      {Node}
    </Tree>
  );
};

const INDENT_STEP = 15;

const Node = ({ node, style, dragHandle }: NodeRendererProps<FileInfo>) => {
  const Icon = node.isInternal ? FolderIcon : FileIcon;

  return (
    <div
      ref={dragHandle}
      style={style}
      className="flex items-center cursor-pointer gap-2 ml-2 text-muted-foreground whitespace-nowrap"
      onClick={() => node.isInternal && node.toggle()}
    >
      <FolderArrow node={node} />
      <Icon className="w-5 h-5 flex-shrink-0" /> <span>{node.data.name}</span>
    </div>
  );
};

const FolderArrow = ({ node }: { node: NodeApi<FileInfo> }) => {
  if (!node.data.isDirectory) {
    return <span className="w-5 h-5 flex-shrink-0" />;
  }

  return node.isOpen ? (
    <ChevronDownIcon className="w-5 h-5 flex-shrink-0" />
  ) : (
    <ChevronRightIcon className="w-5 h-5 flex-shrink-0" />
  );
};
