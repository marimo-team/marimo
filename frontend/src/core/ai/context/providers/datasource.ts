/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { createRoot } from "react-dom/client";
import { dbDisplayName } from "@/components/databases/display";
import { renderDatasourceInfo } from "@/core/codemirror/language/languages/sql/renderers";
import type { ConnectionsMap } from "@/core/datasets/data-source-connections";
import type { DataSourceConnection } from "@/core/kernel/messages";
import type { AIContextItem } from "../registry";
import { AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Boosts } from "./common";

export interface DatasourceContextItem extends AIContextItem {
  type: "datasource";
  data: DataSourceConnection;
}

export class DatasourceContextProvider extends AIContextProvider<DatasourceContextItem> {
  readonly title = "Datasource";
  readonly mentionPrefix = "@";
  readonly contextType = "datasource";
  private connectionsMap: ConnectionsMap;

  constructor(connectionsMap: ConnectionsMap) {
    super();
    this.connectionsMap = connectionsMap;
  }

  getItems(): DatasourceContextItem[] {
    return [...this.connectionsMap.values()].map((connection) => ({
      uri: this.asURI(connection.name),
      name: connection.name,
      type: this.contextType,
      data: connection,
    }));
  }

  formatContext(item: DatasourceContextItem): string {
    return contextToXml({
      type: this.contextType,
      data: item.data,
    });
  }

  formatCompletion(item: DatasourceContextItem): Completion {
    const connection = item.data;

    return {
      label: `@${connection.name}`,
      displayLabel: connection.name,
      detail: dbDisplayName(connection.dialect),
      boost: Boosts.LOW,
      type: "datasource",
      apply: `@${connection.name}`,
      section: "Data Sources",
      info: () => {
        const infoContainer = document.createElement("div");
        infoContainer.classList.add("mo-cm-tooltip", "docs-documentation");

        // Use React to render the datasource info
        const root = createRoot(infoContainer);
        root.render(renderDatasourceInfo(connection));

        return infoContainer;
      },
    };
  }
}
