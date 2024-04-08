/* Copyright 2024 Marimo. All rights reserved. */
import { documentationAtom } from "@/core/documentation/state";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { useAtomValue } from "jotai";
import React from "react";
import "../../documentation.css";
import { BookMarkedIcon } from "lucide-react";
import { PanelEmptyState } from "./empty-state";

export const DocumentationPanel: React.FC = () => {
  const { documentation } = useAtomValue(documentationAtom);

  if (!documentation) {
    return (
      <PanelEmptyState
        title="No documentation"
        description="Move your cursor over a symbol to see its documentation."
        icon={<BookMarkedIcon />}
      />
    );
  }

  return (
    <div className="p-3 overflow-y-auto overflow-x-hidden h-full docs-documentation flex flex-col gap-4">
      {renderHTML({ html: documentation })}
    </div>
  );
};
