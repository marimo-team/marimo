/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { createRoot } from "react-dom/client";
import { dbDisplayName } from "@/components/databases/display";
import { renderDatasourceInfo } from "@/core/codemirror/language/languages/sql/renderers";
import {
  type ConnectionsMap,
  type DatasetTablesMap,
  getTableType,
} from "@/core/datasets/data-source-connections";
import {
  type ConnectionName,
  INTERNAL_SQL_ENGINES,
} from "@/core/datasets/engines";
import type { DataSourceConnection, DataTable } from "@/core/kernel/messages";
import type { AIContextItem } from "../registry";
import { AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Boosts } from "./common";

export interface DatasourceContextItem extends AIContextItem {
  type: "datasource";
  // For internal engine, it can have both datasource and data tables
  // For external engines, the data is a DataSourceConnection
  data: {
    datasource: DataSourceConnection;
    tables?: DataTable[];
  };
}

export class DatasourceContextProvider extends AIContextProvider<DatasourceContextItem> {
  readonly title = "Datasource";
  readonly mentionPrefix = "@";
  readonly contextType = "datasource";
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
    return [...this.connectionsMap.values()].map((connection) => {
      let description = "Database schema";
      const data: DatasourceContextItem["data"] = {
        datasource: connection,
      };
      if (INTERNAL_SQL_ENGINES.has(connection.name)) {
        data.tables = this.dataframes;
        description = "Database schema and the dataframes that can be queried";
      }

      return {
        uri: this.asURI(connection.name),
        name: connection.name,
        description: description,
        type: this.contextType,
        data: data,
      };
    });
  }

  formatContext(item: DatasourceContextItem): string {
    const data = item.data;
    // Remove certain fields that are not needed in the context
    const { name, display_name, source, ...filteredDatasource } =
      data.datasource;

    return contextToXml({
      type: this.contextType,
      data: {
        datasource: filteredDatasource,
        tables: data.tables,
      },
    });
  }

  formatCompletion(item: DatasourceContextItem): Completion {
    const connection = item.data;

    const datasource = connection.datasource;
    const dataframes = connection.tables;

    let label = datasource.name;
    if (INTERNAL_SQL_ENGINES.has(datasource.name as ConnectionName)) {
      label = "In-Memory";
    }

    return {
      label: `@${label}`,
      displayLabel: label,
      detail: dbDisplayName(datasource.dialect),
      boost: Boosts.LOW,
      type: this.contextType,
      section: "Data Sources",
      info: () => {
        const infoContainer = document.createElement("div");
        infoContainer.classList.add("mo-cm-tooltip", "docs-documentation");

        // Use React to render the datasource info
        const root = createRoot(infoContainer);
        root.render(renderDatasourceInfo(datasource, dataframes));

        return infoContainer;
      },
    };
  }
}
