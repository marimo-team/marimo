/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect } from "react";
import type { NodeApi } from "react-arborist";
import type { FileTreeNode } from "./requesting-tree";

export const HOVER_EXPAND_DELAY = 600;

export function useHoverExpand(
  node: NodeApi<FileTreeNode>,
  isHovering: boolean,
) {
  const tree = node.tree;
  useEffect(() => {
    if (!isHovering || !node.data.isDirectory || node.isOpen) {
      return;
    }
    const timeout = window.setTimeout(
      () => tree.open(node.id),
      HOVER_EXPAND_DELAY,
    );
    return () => window.clearTimeout(timeout);
  }, [isHovering, node.data.isDirectory, node.isOpen, node.id, tree]);
}
