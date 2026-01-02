/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { createRoot } from "react-dom/client";
import { dbDisplayName } from "@/components/databases/display";
import { cellDataAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { LanguageAdapters } from "@/core/codemirror/language/LanguageAdapters";
import { renderDatasourceInfo } from "@/core/codemirror/language/languages/sql/renderers";
import {
  type ConnectionsMap,
  type DatasetTablesMap,
  dataSourceConnectionsAtom,
  getTableType,
} from "@/core/datasets/data-source-connections";
import {
  type ConnectionName,
  INTERNAL_SQL_ENGINES,
} from "@/core/datasets/engines";
import type { DataSourceConnection, DataTable } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import type { AIContextItem } from "../registry";
import { AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Boosts, Sections } from "./common";

type NamedDatasource = Omit<
  DataSourceConnection,
  "name" | "display_name" | "source"
> & {
  // Easier for the AI to write mo.sql with engine name
  engine_name?: ConnectionName;
};

export interface DatasourceContextItem extends AIContextItem {
  type: "datasource";
  // For internal engine, it can have both connection and data tables
  // For external engines, the data is just a DataSourceConnection
  data: {
    connection: DataSourceConnection;
    tables?: DataTable[];
  };
}

const CONTEXT_TYPE = "datasource";

export class DatasourceContextProvider extends AIContextProvider<DatasourceContextItem> {
  readonly title = "Datasource";
  readonly mentionPrefix = "@";
  readonly contextType = CONTEXT_TYPE;
  private connectionsMap: ConnectionsMap;
  private dataframes: DataTable[];

  constructor(connectionsMap: ConnectionsMap, tablesMap: DatasetTablesMap) {
    super();
    this.connectionsMap = connectionsMap;
    this.dataframes = [...tablesMap.values()].filter(
      (table: DataTable) => getTableType(table) === "dataframe",
    );
  }

  getItems(): DatasourceContextItem[] {
    return [...this.connectionsMap.values()]
      .map((connection): DatasourceContextItem | null => {
        let description = "Database schema.";
        const data: DatasourceContextItem["data"] = {
          connection: connection,
        };

        if (INTERNAL_SQL_ENGINES.has(connection.name)) {
          data.tables = this.dataframes;
          description =
            "Database schema and the dataframes that can be queried";
        }

        // Hide empty datasources
        const hasNoTables =
          connection.databases.length === 0 && (data.tables?.length ?? 0) === 0;
        if (hasNoTables) {
          return null;
        }

        return {
          uri: this.asURI(connection.name),
          name: connection.name,
          description: description,
          type: this.contextType,
          data: data,
        };
      })
      .filter(Boolean);
  }

  formatContext(item: DatasourceContextItem): string {
    const data = item.data;
    // Remove certain fields that are not needed in the context
    const { name, display_name, source, ...filteredDatasource } =
      data.connection;

    let datasource = filteredDatasource;
    const isInternalEngine = INTERNAL_SQL_ENGINES.has(name as ConnectionName);
    if (!isInternalEngine) {
      const namedDatasource: NamedDatasource = {
        ...filteredDatasource,
        engine_name: name as ConnectionName, // Add the engine name for external engines
      };
      datasource = namedDatasource;
    }

    return contextToXml({
      type: this.contextType,
      data: {
        connection: datasource,
        tables: data.tables,
      },
    });
  }

  formatCompletion(item: DatasourceContextItem): Completion {
    const datasource = item.data;

    const dataConnection = datasource.connection;
    const dataframes = datasource.tables;

    let label = dataConnection.name;
    if (INTERNAL_SQL_ENGINES.has(dataConnection.name as ConnectionName)) {
      label = "In-Memory";
    }

    return {
      label: `@${label}`,
      displayLabel: label,
      detail: dbDisplayName(dataConnection.dialect),
      boost: Boosts.MEDIUM,
      type: this.contextType,
      section: Sections.DATA_SOURCES,
      info: () => {
        const infoContainer = document.createElement("div");
        infoContainer.classList.add("mo-cm-tooltip", "docs-documentation");

        // Use React to render the datasource info
        const root = createRoot(infoContainer);
        root.render(renderDatasourceInfo(dataConnection, dataframes));

        return infoContainer;
      },
    };
  }
}

export function getDatasourceContext(cellId: CellId): string | null {
  const cellData = store.get(cellDataAtom(cellId));
  const code = cellData?.code;
  if (!code || code.trim() === "") {
    return null;
  }

  const [_sqlStatement, _, metadata] = LanguageAdapters.sql.transformIn(code);
  const datasourceSchema = store
    .get(dataSourceConnectionsAtom)
    .connectionsMap.get(metadata.engine);
  if (datasourceSchema) {
    return `@${CONTEXT_TYPE}://${datasourceSchema.name}`;
  }
  return null;
}
