/* Copyright 2026 Marimo. All rights reserved. */
import type { TypedString } from "@/utils/typed";

export type ConnectionName = TypedString<"ConnectionName">;

// DuckDB engine is treated as the default engine
// As it doesn't require passing an engine variable to the backend
// Keep this in sync with the backend name
export const DUCKDB_ENGINE = "__marimo_duckdb" as ConnectionName;
export const POLARS_ENGINE = "__marimo_polars" as ConnectionName;
export const INTERNAL_SQL_ENGINES = new Set([DUCKDB_ENGINE, POLARS_ENGINE]);
export const DEFAULT_DUCKDB_DATABASE = "memory";
