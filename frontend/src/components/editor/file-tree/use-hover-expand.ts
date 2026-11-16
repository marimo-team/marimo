/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef } from "react";
import type { NodeApi } from "react-arborist";
import type { FileTreeNode } from "./requesting-tree";

export const HOVER_EXPAND_DELAY = 600;

export function useHoverExpand(
  node: NodeApi<FileTreeNode>,
  isHovering: boolean,
) {
  const tree = node.tree;
  const attemptedNode = useRef<string | null>(null);
  useEffect(() => {
    if (!isHovering) {
      attemptedNode.current = null;
      return;
    }
    if (
      !node.data.isDirectory ||
      node.isOpen ||
      attemptedNode.current === node.id
    ) {
      return;
    }
    const timeout = window.setTimeout(() => {
      // A failed load closes the folder. Retry only after leaving and reentering.
      attemptedNode.current = node.id;
      tree.open(node.id);
    }, HOVER_EXPAND_DELAY);
    return () => window.clearTimeout(timeout);
  }, [isHovering, node.data.isDirectory, node.isOpen, node.id, tree]);
}
