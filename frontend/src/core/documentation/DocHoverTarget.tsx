/* Copyright 2026 Marimo. All rights reserved. */

import type { ReactNode } from "react";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { requestOutputDocumentation } from "./doc-lookup";

export const DocHoverTarget: React.FC<{
  qualifiedName: string;
  children: ReactNode;
}> = ({ qualifiedName, children }) => {
  const handleMouseEnter = useDebouncedCallback(() => {
    requestOutputDocumentation(qualifiedName);
  }, 100);

  return (
    <span
      onMouseEnter={handleMouseEnter}
      onMouseLeave={() => handleMouseEnter.cancel()}
    >
      {children}
    </span>
  );
};
