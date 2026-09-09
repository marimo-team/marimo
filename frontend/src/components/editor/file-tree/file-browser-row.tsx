/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef } from "react";
import type { RowRendererProps } from "react-arborist";
import { useDrop } from "react-dnd";
import { FileTreeRow } from "./file-tree-row";
import type { FileTreeNode } from "./requesting-tree";

export function FileBrowserRow(props: RowRendererProps<FileTreeNode>) {
  return props.node.data.isDirectory ? (
    <FolderDropRow {...props} />
  ) : (
    <FileTreeRow {...props} />
  );
}

const HOVER_ROW_EXPAND_DELAY = 600;

function FolderDropRow(props: RowRendererProps<FileTreeNode>) {
  const { node } = props;
  const tree = node.tree;
  const rowRef = useRef<HTMLDivElement | null>(null);
  const [{ isHovering }, dropRef] = useDrop(
    () => ({
      // Arborist's drag source uses NODE. Keep its validation and move handler,
      // but treat the entire folder row as a destination, without reorder zones.
      accept: "NODE",
      canDrop: () => tree.canDrop(),
      collect: (monitor) => ({
        isHovering: monitor.isOver({ shallow: true }) && monitor.canDrop(),
      }),
      hover: () => {
        if (
          tree.state.dnd.parentId !== node.id ||
          tree.state.dnd.index !== null
        ) {
          tree.dispatch({
            type: "DND_HOVERING",
            parentId: node.id,
            index: null,
          });
        }
        if (!tree.canDrop()) {
          tree.hideCursor();
        }
      },
      drop: () => {
        if (!tree.canDrop()) {
          return;
        }
        void tree.props.onMove?.({
          dragIds: tree.state.dnd.dragIds,
          dragNodes: tree.dragNodes,
          parentId: node.id,
          parentNode: node,
          index: 0,
        });
        tree.open(node.id);
      },
    }),
    [tree, node.id],
  );

  useEffect(() => {
    if (!isHovering || node.isOpen) {
      return;
    }
    const timeout = window.setTimeout(() => {
      if (
        tree.state.dnd.parentId === node.id &&
        tree.state.dnd.dragIds.length > 0 &&
        tree.canDrop()
      ) {
        tree.open(node.id);
      }
    }, HOVER_ROW_EXPAND_DELAY);
    return () => window.clearTimeout(timeout);
  }, [isHovering, node.isOpen, tree, node.id]);

  // Replacing innerRef avoids attaching Arborist's positional drop target.
  // Retain its focus behavior for keyboard navigation and rename completion.
  useEffect(() => {
    if (node.isFocused && !node.isEditing) {
      rowRef.current?.focus({ preventScroll: true });
    }
  }, [node.isFocused, node.isEditing]);

  return (
    <FileTreeRow
      {...props}
      innerRef={(element) => {
        rowRef.current = element;
        dropRef(element);
      }}
    />
  );
}
