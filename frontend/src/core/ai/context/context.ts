/* Copyright 2024 Marimo. All rights reserved. */

import { allTablesAtom } from "@/core/datasets/data-source-connections";
import { getRequestClient } from "@/core/network/requests";
import type { JotaiStore } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import { CellOutputContextProvider } from "./providers/cell-output";
import { ErrorContextProvider } from "./providers/error";
import { FileContextProvider } from "./providers/file";
import { TableContextProvider } from "./providers/tables";
import { VariableContextProvider } from "./providers/variable";
import { AIContextRegistry } from "./registry";

export function getAIContextRegistry(store: JotaiStore) {
  const tablesMap = store.get(allTablesAtom);
  const variables = store.get(variablesAtom);

  return new AIContextRegistry()
    .register(new TableContextProvider(tablesMap))
    .register(new VariableContextProvider(variables, tablesMap))
    .register(new ErrorContextProvider(store))
    .register(new CellOutputContextProvider(store));
}

export function getFileContextProvider(): FileContextProvider {
  const apiRequests = getRequestClient();
  return new FileContextProvider(apiRequests);
}
