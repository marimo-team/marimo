/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ChartBarIcon, Code2Icon } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ChartSpec } from "@/plugins/impl/data-explorer/state/types";
import { DataExplorerComponent } from "@/plugins/impl/data-explorer/ConnectedDataExplorerComponent";

export const Charts = () => {
  const [value, setValue] = useState<ChartSpec>();
  return (
    <DataExplorerComponent
      data="https://raw.githubusercontent.com/kirenz/datasets/b8f17b8fc4907748b3317554d65ffd780edcc057/gapminder.csv"
      value={value}
      setValue={(v) => {
        setValue(v);
      }}
    />
  );
};

export const AddTabContextMenu = () => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button variant="text" size="icon">
          +
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem>
          <ChartBarIcon className="w-3 h-3 mr-2" />
          Add chart
        </DropdownMenuItem>
        <DropdownMenuItem>
          <Code2Icon className="w-3 h-3 mr-2" />
          Add transform
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
