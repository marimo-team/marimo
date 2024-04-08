/* Copyright 2024 Marimo. All rights reserved. */
import { VariableTable } from "@/components/variables/variables-table";
import { useCellIds } from "@/core/cells/cells";
import { useVariables } from "@/core/variables/state";
import React from "react";
import { PanelEmptyState } from "./empty-state";
import { FunctionSquareIcon } from "lucide-react";

export const VariablePanel: React.FC = () => {
  const variables = useVariables();
  const cellIds = useCellIds();

  if (Object.keys(variables).length === 0) {
    return (
      <PanelEmptyState
        title="No variables"
        description="Global variables will appear here."
        icon={<FunctionSquareIcon />}
      />
    );
  }

  return (
    <VariableTable className="flex-1" cellIds={cellIds} variables={variables} />
  );
};
