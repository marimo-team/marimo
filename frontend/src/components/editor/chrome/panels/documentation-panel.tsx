/* Copyright 2024 Marimo. All rights reserved. */
import { documentationAtom } from "@/core/documentation/state";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { useAtomValue } from "jotai";
import React from "react";
import "../../documentation.css";
import { BookMarkedIcon } from "lucide-react";

export const DocumentationPanel: React.FC = () => {
  const { documentation } = useAtomValue(documentationAtom);

  if (!documentation) {
    return (
      <div className="mx-6 my-6 flex flex-row gap-2 items-center rounded-lg">
        <BookMarkedIcon className="text-accent-foreground" />
        <span className="mt-[0.25rem] text-accent-foreground">
          No documentation
        </span>
      </div>
    );
  }

  return (
    <div className="p-3 overflow-y-auto overflow-x-hidden h-full docs-documentation flex flex-col gap-4">
      {renderHTML({ html: documentation })}
    </div>
  );
};
