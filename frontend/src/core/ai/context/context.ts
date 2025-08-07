/* Copyright 2024 Marimo. All rights reserved. */
import { allTablesAtom } from "@/core/datasets/data-source-connections";
import type { JotaiStore } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import {
  TableContextProvider,
  VariableContextProvider,
} from "./providers/context-providers";
import { AIContextRegistry } from "./registry";

export function getAIContextRegistry(store: JotaiStore) {
  const tablesMap = store.get(allTablesAtom);
  const variables = store.get(variablesAtom);
  return new AIContextRegistry()
    .register(new TableContextProvider(tablesMap))
    .register(new VariableContextProvider(variables, tablesMap));
}
