/* Copyright 2023 Marimo. All rights reserved. */
import { VariableTable } from "@/components/variables/variables-table";
import { useCellIds } from "@/core/cells/cells";
import { useVariables } from "@/core/variables/state";
import React from "react";

export const VariablePanel: React.FC = () => {
  const variables = useVariables();
  const cellIds = useCellIds();

  return (
    <VariableTable className="flex-1" cellIds={cellIds} variables={variables} />
  );
};
