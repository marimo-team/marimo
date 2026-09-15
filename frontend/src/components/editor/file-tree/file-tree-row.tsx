/* Copyright 2026 Marimo. All rights reserved. */

import type { RowRendererProps } from "react-arborist";
import type { FileTreeNode } from "./requesting-tree";

export function FileTreeRow({
  node,
  attrs,
  innerRef,
  children,
  ariaLabel = node.data.name,
}: RowRendererProps<FileTreeNode> & { ariaLabel?: string }) {
  return (
    <div
      {...attrs}
      ref={innerRef}
      aria-label={ariaLabel}
      aria-expanded={node.isInternal ? node.isOpen : undefined}
      onFocus={(event) => {
        event.stopPropagation();
        attrs.onFocus?.(event);
        if (event.target === event.currentTarget && !node.isFocused) {
          node.focus();
        }
      }}
      onClick={(event) => {
        if (attrs.onClick) {
          attrs.onClick(event);
        } else {
          node.select();
        }
        if (!event.defaultPrevented) {
          event.currentTarget.focus({ preventScroll: true });
        }
      }}
    >
      {children}
    </div>
  );
}
