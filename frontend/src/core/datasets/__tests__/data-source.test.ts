/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import { variableName } from "@/__tests__/branded";
import {
  findNodeAtPath,
  isDataTableNode,
  isNamespaceNode,
  isSchemaNode,
} from "../catalog";
import { catalogPathKey } from "../catalog-load-state";
import type {
  Database,
  DatabaseNamespace,
  DatabaseSchema,
  DataTable,
} from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import type { VariableName } from "@/core/variables/types";
import {
  allTablesAtom,
  type DataSourceConnectionInput,
  dataSourceConnectionsAtom,
  type DataSourceState,
  exportedForTesting,
  type SQLTableContext,
} from "../data-source-connections";
import { type ConnectionName, INTERNAL_SQL_ENGINES } from "../engines";

const { reducer, initialState } = exportedForTesting;

function makeSchema(name: string, tables: DataTable[] = []): DatabaseSchema {
  return { kind: "schema", name, tables };
}

function makeTable(
  name: string,
  overrides: Partial<DataTable> = {},
): DataTable {
  return {
    kind: "data_table",
    name,
    columns: [],
    num_columns: 0,
    num_rows: 0,
    variable_name: null,
    source: "",
    source_type: "local",
    type: "table",
    ...overrides,
  };
}

function schemaFromChildren(
  children: Database["children"],
  name: string,
): DatabaseSchema | undefined {
  const node = children.find(
    (child) => isSchemaNode(child) && child.name === name,
  );
  return node && isSchemaNode(node) ? node : undefined;
}

// Helper function to add connections
function addConnection(
  connections: DataSourceConnectionInput[],
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
    expect(
      newState.connectionsMap.get("conn1" as ConnectionName),
    ).toMatchObject(newConnections[0]);
    expect(
      newState.connectionsMap.get("conn1" as ConnectionName)?.catalogLoad,
    ).toEqual({ childrenLoaded: new Set(), tablesLoaded: new Set() });
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
    expect(
      newState.connectionsMap.get("conn1" as ConnectionName),
    ).toMatchObject(updatedConnection);
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
    const filtered = filterDataSources([variableName("conn1")]);
    expect(filtered.connectionsMap.size).toBe(defaultConnSize + 1);
    expect(filtered.connectionsMap.has("conn1" as ConnectionName)).toBe(true);
    for (const engine of INTERNAL_SQL_ENGINES) {
      expect(filtered.connectionsMap.has(engine)).toBe(true);
    }
  });

  it("filters out non-matching variables", () => {
    const filtered = filterDataSources([variableName("non_existent")]);
    expect(filtered.connectionsMap.size).toBe(defaultConnSize);
  });

  it("handles mix of matching and non-matching variables", () => {
    const filtered = filterDataSources([
      variableName("conn1"),
      variableName("non_existent"),
    ]);
    expect(filtered.connectionsMap.size).toBe(defaultConnSize + 1);
    expect(filtered.connectionsMap.has("conn1" as ConnectionName)).toBe(true);
    for (const engine of INTERNAL_SQL_ENGINES) {
      expect(filtered.connectionsMap.has(engine)).toBe(true);
    }
  });
});

describe("add schema list", () => {
  const connections: DataSourceConnectionInput[] = [
    {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [
        {
          name: "db1",
          children: [],
          dialect: "sqlite",
        },
      ],
    },
  ];

  // Helper function to add schema list
  const addSchemaList = (
    schemas: DatabaseSchema[],
    engine: string,
    database: string,
  ) => {
    return reducer(baseState, {
      type: "addSchemaList",
      payload: {
        nodes: schemas,
        sqlSchemaContext: { engine, database },
      },
    });
  };

  let baseState: DataSourceState;

  beforeEach(() => {
    baseState = addConnection(connections, baseState);
    expect(baseState.connectionsMap.size).toBe(defaultConnSize + 1);
  });

  it("adds schema list to a specific database", () => {
    const schemaList: DatabaseSchema[] = [
      makeSchema("public"),
      makeSchema("analytics"),
    ];
    const newState = addSchemaList(schemaList, "conn1", "db1");

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    expect(db1?.children).toEqual(schemaList);
  });

  it("updates schema list for a database", () => {
    const schemaList: DatabaseSchema[] = [
      makeSchema("public"),
      makeSchema("analytics"),
    ];
    const newState = addSchemaList(schemaList, "conn1", "db1");

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    expect(db1?.children).toEqual(schemaList);

    // update with new schema list
    const newSchemaList: DatabaseSchema[] = [
      makeSchema("public"),
      makeSchema("sales"),
    ];
    const updatedState = addSchemaList(newSchemaList, "conn1", "db1");

    const newConn = updatedState.connectionsMap.get("conn1" as ConnectionName);
    const newDb1 = newConn?.databases.find((db) => db.name === "db1");
    expect(newDb1?.children).toEqual(newSchemaList);
  });

  it("does not add schema list if database does not exist", () => {
    const schemaList: DatabaseSchema[] = [
      makeSchema("public"),
      makeSchema("analytics"),
    ];
    const newState = addSchemaList(schemaList, "conn1", "non_existent_db");

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    expect(db1?.children.length).toBe(0);
  });
});

describe("add table list", () => {
  const connections: DataSourceConnectionInput[] = [
    {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [
        {
          name: "db1",
          children: [makeSchema("public")],
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
    const tableList: DataTable[] = [makeTable("table1")];
    const newState = addTableList(tableList, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
      dialect: "sqlite",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = schemaFromChildren(db1?.children ?? [], "public");
    expect(schema?.tables).toEqual(tableList);
  });

  it("updates table list for a connection", () => {
    const sqlTableContext = {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
      dialect: "sqlite",
    };

    const tableList: DataTable[] = [makeTable("table2")];
    const newState = addTableList(tableList, sqlTableContext);

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = schemaFromChildren(db1?.children ?? [], "public");
    expect(schema?.tables).toEqual(tableList);

    // update with new table list
    const newTableList: DataTable[] = [makeTable("table1")];
    const updatedState = addTableList(newTableList, sqlTableContext);

    const newConn = updatedState.connectionsMap.get("conn1" as ConnectionName);
    const newDb1 = newConn?.databases.find((db) => db.name === "db1");
    const newSchema = schemaFromChildren(newDb1?.children ?? [], "public");
    expect(newSchema?.tables).toEqual(newTableList);
  });

  it("does not add table list if schema does not exist", () => {
    const tableList: DataTable[] = [makeTable("table2")];
    const newState = addTableList(tableList, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "non_existent",
      dialect: "sqlite",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    expect(db1?.children.length).toBe(1);
  });
});

describe("add table", () => {
  const connections: DataSourceConnectionInput[] = [
    {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [
        {
          name: "db1",
          children: [makeSchema("public")],
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
    const table = makeTable("table1");
    const newState = addTable(table, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
      dialect: "sqlite",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = schemaFromChildren(db1?.children ?? [], "public");
    expect(schema?.tables).toEqual([table]);
  });

  it("updates table for a connection", () => {
    const sqlTableContext = {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "public",
      dialect: "sqlite",
    };

    const table = makeTable("table1");
    const newState = addTable(table, sqlTableContext);

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    const schema = schemaFromChildren(db1?.children ?? [], "public");
    expect(schema?.tables).toEqual([table]);

    // update details of same table
    const updatedTable = makeTable("table1", { source: "new_source" });

    const updatedState = addTable(updatedTable, sqlTableContext);

    const newConn = updatedState.connectionsMap.get("conn1" as ConnectionName);
    const newDb1 = newConn?.databases.find((db) => db.name === "db1");
    const newSchema = schemaFromChildren(newDb1?.children ?? [], "public");
    expect(newSchema?.tables).toEqual([updatedTable]);
  });

  it("does not add table if schema does not exist", () => {
    const table = makeTable("table2");
    const newState = addTable(table, {
      engine: "conn1" as ConnectionName,
      database: "db1",
      schema: "non_existent",
      dialect: "sqlite",
    });

    const conn1 = newState.connectionsMap.get("conn1" as ConnectionName);
    const db1 = conn1?.databases.find((db) => db.name === "db1");
    expect(db1?.children.length).toBe(1);
  });
});

describe("nested namespaces", () => {
  const nestedNamespace = (
    name: string,
    overrides: Partial<DatabaseNamespace> = {},
  ): DatabaseNamespace => ({
    kind: "namespace",
    name,
    children: [],
    ...overrides,
  });

  const nestedConnections: DataSourceConnectionInput[] = [
    {
      name: "ice" as ConnectionName,
      source: "iceberg",
      display_name: "Iceberg",
      dialect: "iceberg",
      databases: [
        {
          name: "top",
          dialect: "iceberg",
          children: [makeSchema("", []), nestedNamespace("nested")],
        },
      ],
    },
  ];

  let baseState: DataSourceState;

  beforeEach(() => {
    baseState = addConnection(nestedConnections, initialState());
  });

  const findNode = (state: DataSourceState, path: string[]) => {
    const conn = state.connectionsMap.get("ice" as ConnectionName);
    const db = conn?.databases.find((d) => d.name === "top");
    return db ? findNodeAtPath({ nodes: db.children, path }) : undefined;
  };

  it("sets child namespaces at a nested path", () => {
    const children: DatabaseSchema[] = [makeSchema("deep", [])];
    const newState = reducer(baseState, {
      type: "addSchemaList",
      payload: {
        nodes: children,
        sqlSchemaContext: {
          engine: "ice",
          database: "top",
          schemaPath: ["nested"],
        },
      },
    });

    const nested = findNode(newState, ["nested"]);
    expect(isNamespaceNode(nested!)).toBe(true);
    if (isNamespaceNode(nested!)) {
      expect(nested.children.map((child) => child.name)).toEqual(["deep"]);
    }
    const conn = newState.connectionsMap.get("ice" as ConnectionName);
    expect(conn).toBeDefined();
    expect(
      conn!.catalogLoad.childrenLoaded.has(catalogPathKey("top", ["nested"])),
    ).toBe(true);
    expect(findNode(newState, [""])?.name).toBe("");
  });

  it("sets tables at a nested path", () => {
    const tables: DataTable[] = [
      makeTable("table4", { source: "iceberg", source_type: "catalog" }),
    ];
    const newState = reducer(baseState, {
      type: "addTableList",
      payload: {
        tables,
        sqlTableContext: {
          engine: "ice",
          database: "top",
          schema: "nested",
          dialect: "iceberg",
          schemaPath: ["nested"],
        },
      },
    });

    const nested = findNode(newState, ["nested"]);
    expect(isNamespaceNode(nested!)).toBe(true);
    if (isNamespaceNode(nested!)) {
      expect(nested.children.map((child) => child.name)).toEqual(["table4"]);
    }
    const conn = newState.connectionsMap.get("ice" as ConnectionName);
    expect(conn).toBeDefined();
    expect(
      conn!.catalogLoad.tablesLoaded.has(catalogPathKey("top", ["nested"])),
    ).toBe(true);
  });

  it("sets tables on a schema nested inside a namespace", () => {
    const tables: DataTable[] = [
      makeTable("table4", { source: "iceberg", source_type: "catalog" }),
    ];
    const withNestedSchema = reducer(baseState, {
      type: "addSchemaList",
      payload: {
        nodes: [makeSchema("deep")],
        sqlSchemaContext: {
          engine: "ice",
          database: "top",
          schemaPath: ["nested"],
        },
      },
    });

    const newState = reducer(withNestedSchema, {
      type: "addTableList",
      payload: {
        tables,
        sqlTableContext: {
          engine: "ice",
          database: "top",
          schema: "deep",
          dialect: "iceberg",
          schemaPath: ["nested"],
        },
      },
    });

    const deep = findNode(newState, ["nested", "deep"]);
    expect(isSchemaNode(deep!)).toBe(true);
    if (isSchemaNode(deep!)) {
      expect(deep.tables).toEqual(tables);
    }
    const nested = findNode(newState, ["nested"]);
    expect(isNamespaceNode(nested!)).toBe(true);
    if (isNamespaceNode(nested!)) {
      expect(nested.children.filter(isDataTableNode)).toHaveLength(0);
    }
    const conn = newState.connectionsMap.get("ice" as ConnectionName);
    expect(conn).toBeDefined();
    expect(
      conn!.catalogLoad.tablesLoaded.has(
        catalogPathKey("top", ["nested", "deep"]),
      ),
    ).toBe(true);
    expect(
      conn!.catalogLoad.tablesLoaded.has(catalogPathKey("top", ["nested"])),
    ).toBe(false);
  });

  it("replaces a single table at a nested path", () => {
    const catalogTable = (numRows: number) =>
      makeTable("table4", {
        num_rows: numRows,
        source: "iceberg",
        source_type: "catalog",
      });
    const context = {
      engine: "ice",
      database: "top",
      schema: "nested",
      dialect: "iceberg",
      schemaPath: ["nested"],
    };
    let state = reducer(baseState, {
      type: "addTableList",
      payload: { tables: [catalogTable(1)], sqlTableContext: context },
    });
    state = reducer(state, {
      type: "addTable",
      payload: { table: catalogTable(42), sqlTableContext: context },
    });

    const nested = findNode(state, ["nested"]);
    expect(isNamespaceNode(nested!)).toBe(true);
    if (isNamespaceNode(nested!)) {
      const tableNodes = nested.children.filter(isDataTableNode);
      expect(tableNodes).toHaveLength(1);
      expect(tableNodes[0].num_rows).toBe(42);
    }
  });

  it("does not change anything for a missing nested path", () => {
    const newState = reducer(baseState, {
      type: "addSchemaList",
      payload: {
        nodes: [makeSchema("deep")],
        sqlSchemaContext: {
          engine: "ice",
          database: "top",
          schemaPath: ["does_not_exist"],
        },
      },
    });
    const newDb = newState.connectionsMap
      .get("ice" as ConnectionName)
      ?.databases.find((d) => d.name === "top");
    const nested = findNode(newState, ["nested"]);
    expect(isNamespaceNode(nested!)).toBe(true);
    const conn = newState.connectionsMap.get("ice" as ConnectionName);
    expect(conn).toBeDefined();
    expect(
      conn!.catalogLoad.childrenLoaded.has(catalogPathKey("top", ["nested"])),
    ).toBe(false);
    expect(newDb?.children.length).toBe(2);
  });
});

describe("allTablesAtom with nested namespaces", () => {
  it("enumerates tables from nested namespaces", () => {
    const catalogTable = (name: string) =>
      makeTable(name, { source: "iceberg", source_type: "catalog" });

    const state = addConnection(
      [
        {
          name: "ice" as ConnectionName,
          source: "iceberg",
          display_name: "Iceberg",
          dialect: "iceberg",
          databases: [
            {
              name: "top",
              dialect: "iceberg",
              children: [
                makeSchema("", [catalogTable("toptable")]),
                {
                  kind: "namespace",
                  name: "nested",
                  children: [
                    catalogTable("nestedtable"),
                    {
                      kind: "namespace",
                      name: "deep",
                      children: [
                        makeSchema("leaf", [catalogTable("deeptable")]),
                      ],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
      initialState(),
    );

    store.set(dataSourceConnectionsAtom, state);
    const names = [...store.get(allTablesAtom).values()].map((t) => t.name);
    expect(names).toContain("toptable");
    expect(names).toContain("nestedtable");
    expect(names).toContain("deeptable");
  });
});
