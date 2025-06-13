/* Copyright 2024 Marimo. All rights reserved. */

import { FunctionSquareIcon } from "lucide-react";
import type React from "react";
import { VariableTable } from "@/components/variables/variables-table";
import { useCellIds } from "@/core/cells/cells";
import { useVariables } from "@/core/variables/state";
import { PanelEmptyState } from "./empty-state";

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
    <VariableTable
      className="flex-1"
      cellIds={cellIds.inOrderIds}
      variables={variables}
    />
  );
};
