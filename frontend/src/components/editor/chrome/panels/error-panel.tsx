/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { useCellErrors } from "../../../../core/cells/cells";
import { MarimoErrorOutput } from "../../output/MarimoErrorOutput";
import { CellLinkError } from "@/components/editor/links/cell-link";
import { PartyPopperIcon } from "lucide-react";
import { PanelEmptyState } from "./empty-state";

export const ErrorsPanel: React.FC = () => {
  const errors = useCellErrors();

  if (errors.length === 0) {
    return <PanelEmptyState title="No errors!" icon={<PartyPopperIcon />} />;
  }

  return (
    <div className="flex flex-col overflow-auto">
      {errors.map((error) => (
        <div key={error.cellId}>
          <div className="text-xs font-mono font-semibold bg-muted border-y px-2 py-1">
            <CellLinkError cellId={error.cellId} />
          </div>
          <div key={error.cellId} className="px-2">
            <MarimoErrorOutput key={error.cellId} errors={error.output.data} />
          </div>
        </div>
      ))}
    </div>
  );
};
