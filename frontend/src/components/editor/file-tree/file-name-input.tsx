/* Copyright 2026 Marimo. All rights reserved. */

import type { NodeApi } from "react-arborist";
import { useEffect, useRef } from "react";
import type { FileInfo } from "@/core/network/types";

/**
 * Inline rename input used by `react-arborist` nodes when `node.isEditing`
 * is true. Auto-focuses and selects everything except the extension so a
 * user can type straight into the name.
 */
export const FileNameInput = ({ node }: { node: NodeApi<FileInfo> }) => {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
    // Select everything but the extension. For extensionless names
    // (`README`) and dotfiles (`.env`), select the full name.
    const name = node.data.name;
    const dotIndex = name.lastIndexOf(".");
    const end = dotIndex > 0 ? dotIndex : name.length;
    ref.current?.setSelectionRange(0, end);
  }, [node.data.name]);

  return (
    <input
      ref={ref}
      className="flex-1 bg-transparent border border-border text-muted-foreground"
      defaultValue={node.data.name}
      onClick={(e) => e.stopPropagation()}
      onBlur={() => node.reset()}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          node.reset();
        }
        if (e.key === "Enter") {
          node.submit(e.currentTarget.value);
        }
      }}
    />
  );
};
