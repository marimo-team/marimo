/* Copyright 2026 Marimo. All rights reserved. */

import type { RowRendererProps } from "react-arborist";
import type { FileTreeNode } from "./requesting-tree";

export function FileTreeRow({
  node,
  attrs,
  innerRef,
  children,
}: RowRendererProps<FileTreeNode>) {
  return (
    <div
      {...attrs}
      ref={innerRef}
      aria-label={node.data.name}
      aria-expanded={node.isInternal ? node.isOpen : undefined}
      onFocus={(event) => event.stopPropagation()}
      onClick={() => node.select()}
    >
      {children}
    </div>
  );
}
