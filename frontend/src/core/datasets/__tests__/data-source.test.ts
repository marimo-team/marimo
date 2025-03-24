/* Copyright 2024 Marimo. All rights reserved. */
import { expect, it, describe, beforeEach } from "vitest";
import {
  type ConnectionName,
  type DataSourceConnection,
  type DataSourceState,
  exportedForTesting,
  INTERNAL_SQL_ENGINES,
  type SQLTableContext,
} from "../data-source-connections";
import type { VariableName } from "@/core/variables/types";
import type { DataTable } from "@/core/kernel/messages";

const { reducer, initialState } = exportedForTesting;

// Helper function to add connections
function addConnection(
  connections: DataSourceConnection[],
  state: DataSourceState,
): DataSourceState {
  return reducer(state, {
    type: "addDataSourceConnection",
    payload: {
      connections: connections,
    },
  });
}

const defaultConnSize = 1;

describe("data source connections", () => {
  let state: DataSourceState;

  beforeEach(() => {
    state = initialState();
  });

  it("starts with default connections map", () => {
    expect(initialState().connectionsMap.size).toBe(defaultConnSize);
    for (const engine of INTERNAL_SQL_ENGINES) {
      expect(initialState().connectionsMap.has(engine)).toBe(true);
    }
  });

  it("can add new connections", () => {
    const newConnections = [
      {
        name: "conn1" as ConnectionName,
        source: "sqlite",
        display_name: "SQLite DB",
        dialect: "sqlite",
        databases: [],
      },
    ];

    const newState = addConnection(newConnections, state);
    expect(newState.connectionsMap.size).toBe(defaultConnSize + 1);
    expect(newState.connectionsMap.get("conn1" as ConnectionName)).toEqual(
      newConnections[0],
    );
  });

  it("updates existing connections", () => {
    const connection = {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [],
    };

    const updatedConnection = {
      ...connection,
      display_name: "Updated SQLite",
    };

    let newState = addConnection([connection], state);
    newState = addConnection([updatedConnection], state);

    expect(newState.connectionsMap.size).toBe(defaultConnSize + 1);
    expect(newState.connectionsMap.get("conn1" as ConnectionName)).toEqual(
      updatedConnection,
    );
  });

  it("can remove connections", () => {
    const connections = [
      {
        name: "conn1" as ConnectionName,
        source: "sqlite",
        display_name: "SQLite DB",
        dialect: "sqlite",
        databases: [],
      },
      {
        name: "conn2" as ConnectionName,
        source: "postgres",
        dialect: "postgres",
        display_name: "Postgres DB",
        databases: [],
      },
    ];

    let newState = addConnection(connections, state);
    expect(newState.connectionsMap.size).toBe(defaultConnSize + 2);

    newState = reducer(newState, {
      type: "removeDataSourceConnection",
      payload: "conn1" as ConnectionName,
    });
    expect(newState.connectionsMap.size).toBe(defaultConnSize + 1);
    expect(newState.connectionsMap.has("conn2" as ConnectionName)).toBe(true);
  });

  it("can clear all connections", () => {
    const connections = [
      {
        name: "conn1" as ConnectionName,
        source: "sqlite",
        display_name: "SQLite DB",
        dialect: "sqlite",
        databases: [],
      },
      {
        name: "conn2" as ConnectionName,
        source: "postgres",
        display_name: "Postgres DB",
        dialect: "postgres",
        databases: [],
      },
    ];

    let newState = addConnection(connections, state);
    expect(newState.connectionsMap.size).toBe(defaultConnSize + 2);

    newState = reducer(newState, {
      type: "clearDataSourceConnections",
      payload: {},
    });
    expect(newState.connectionsMap.size).toBe(0);
  });
});

describe("filtering data sources", () => {
  // helper function to filter data sources by variable names
  function filterDataSources(payload: VariableName[]) {
    return reducer(baseState, {
      type: "filterDataSourcesFromVariables",
      payload: payload,
    });
  }

  const connections = [
    {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [],
    },
    {
      name: "conn2" as ConnectionName,
      source: "postgres",
      display_name: "Postgres DB",
      dialect: "postgres",
      databases: [],
    },
  ];

  let baseState: DataSourceState;

  beforeEach(() => {
    baseState = addConnection(connections, baseState);
    expect(baseState.connectionsMap.size).toBe(defaultConnSize + 2); // 2 + 2 (default) connections
  });

  it("keeps only internal engines when no variables", () => {
    const filtered = filterDataSources([]);
    expect(filtered.connectionsMap.size).toBe(defaultConnSize);
    for (const engine of INTERNAL_SQL_ENGINES) {
      expect(filtered.connectionsMap.has(engine)).toBe(true);
    }
  });

  it("keeps matching variables and internal engines", () => {
    const filtered = filterDataSources(["conn1" as unknown as VariableName]);
    expect(filtered.connectionsMap.size).toBe(defaultConnSize + 1);
    expect(filtered.connectionsMap.has("conn1" as ConnectionName)).toBe(true);
    for (const engine of INTERNAL_SQL_ENGINES) {
      expect(filtered.connectionsMap.has(engine)).toBe(true);
    }
  });

  it("filters out non-matching variables", () => {
    const filtered = filterDataSources([
      "non_existent" as unknown as VariableName,
    ]);
    expect(filtered.connectionsMap.size).toBe(defaultConnSize);
  });

  it("handles mix of matching and non-matching variables", () => {
    const filtered = filterDataSources([
      "conn1" as unknown as VariableName,
      "non_existent" as unknown as VariableName,
    ]);
    expect(filtered.connectionsMap.size).toBe(defaultConnSize + 1);
    expect(filtered.connectionsMap.has("conn1" as ConnectionName)).toBe(true);
    for (const engine of INTERNAL_SQL_ENGINES) {
      expect(filtered.connectionsMap.has(engine)).toBe(true);
    }
  });
});

describe("add table list", () => {
  const connections: DataSourceConnection[] = [
    {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "public",
              tables: [],
            },
          ],
          dialect: "sqlite",
        },
      ],
    },
  ];

  // Helper function to add table list
  const addTableList = (
    tables: DataTable[],
    sqlTableContext: SQLTableContext,
  ) => {
    return reducer(baseState, {
      type: "addTableList",
      payload: {
        tables: tables,
        sqlTableContext: sqlTableContext,
      },
    });
  };

  let baseState: DataSourceState;

  beforeEach(() => {
    baseState = addConnection(connections, baseState);
    expect(baseState.connectionsMap.size).toBe(defaultConnSize + 1);
  });

  it("adds table list to a specific connection", () => {
    const tableList: DataTable[] = [
      {
        name: "table1",
        columns: [],
        source: "",
        source_type: "local",
        type: "table",
      },
    ];
    const newState = addTableList(tableList, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = db1?.schemas.find((schema) => schema.name === "public");
    expect(schema?.tables).toEqual(tableList);
  });

  it("updates table list for a connection", () => {
    const sqlTableContext = {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
    };

    const tableList: DataTable[] = [
      {
        name: "table2",
        columns: [],
        source: "",
        source_type: "local",
        type: "table",
      },
    ];
    const newState = addTableList(tableList, sqlTableContext);

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = db1?.schemas.find((schema) => schema.name === "public");
    expect(schema?.tables).toEqual(tableList);

    // update with new table list
    const newTableList: DataTable[] = [
      {
        name: "table1",
        columns: [],
        source: "",
        source_type: "local",
        type: "table",
      },
    ];
    const updatedState = addTableList(newTableList, sqlTableContext);

    const newConn = updatedState.connectionsMap.get("conn1" as ConnectionName);
    const newDb1 = newConn?.databases.find((db) => db.name === "db1");
    const newSchema = newDb1?.schemas.find(
      (schema) => schema.name === "public",
    );
    expect(newSchema?.tables).toEqual(newTableList);
  });

  it("does not add table list if schema does not exist", () => {
    const tableList: DataTable[] = [
      {
        name: "table2",
        columns: [],
        source: "",
        source_type: "local",
        type: "table",
      },
    ];
    const newState = addTableList(tableList, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "non_existent",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    expect(db1?.schemas.length).toBe(1);
  });
});

describe("add table", () => {
  const connections: DataSourceConnection[] = [
    {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "public",
              tables: [],
            },
          ],
          dialect: "sqlite",
        },
      ],
    },
  ];

  // Helper function to add table
  const addTable = (table: DataTable, sqlTableContext: SQLTableContext) => {
    return reducer(baseState, {
      type: "addTable",
      payload: {
        table: table,
        sqlTableContext: sqlTableContext,
      },
    });
  };

  let baseState: DataSourceState;

  beforeEach(() => {
    baseState = addConnection(connections, baseState);
    expect(baseState.connectionsMap.size).toBe(defaultConnSize + 1);
  });

  it("adds table to a specific connection", () => {
    const table: DataTable = {
      name: "table1",
      columns: [],
      source: "",
      source_type: "local",
      type: "table",
    };
    const newState = addTable(table, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = db1?.schemas.find((schema) => schema.name === "public");
    expect(schema?.tables).toEqual([table]);
  });

  it("updates table for a connection", () => {
    const sqlTableContext = {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
    };

    const table: DataTable = {
      name: "table1",
      columns: [],
      source: "",
      source_type: "local",
      type: "table",
    };
    const newState = addTable(table, sqlTableContext);

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = db1?.schemas.find((schema) => schema.name === "public");
    expect(schema?.tables).toEqual([table]);

    // update details of same table
    const updatedTable: DataTable = {
      name: "table1",
      columns: [],
      source: "new_source",
      source_type: "local",
      type: "table",
    };

    const updatedState = addTable(updatedTable, sqlTableContext);

    const newConn = updatedState.connectionsMap.get("conn1" as ConnectionName);
    const newDb1 = newConn?.databases.find((db) => db.name === "db1");
    const newSchema = newDb1?.schemas.find(
      (schema) => schema.name === "public",
    );
    expect(newSchema?.tables).toEqual([updatedTable]);
  });

  it("does not add table if schema does not exist", () => {
    const table: DataTable = {
      name: "table2",
      columns: [],
      source: "",
      source_type: "local",
      type: "table",
    };
    const newState = addTable(table, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "non_existent",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    expect(db1?.schemas.length).toBe(1);
  });
});
