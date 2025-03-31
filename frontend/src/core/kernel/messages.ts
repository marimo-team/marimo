/* Copyright 2024 Marimo. All rights reserved. */
import type { components } from "@marimo-team/marimo-api";

export type schemas = components["schemas"];
export type DataType = schemas["DataType"];
export const DATA_TYPES = [
  "string",
  "boolean",
  "integer",
  "number",
  "date",
  "datetime",
  "time",
  "unknown",
] as const;
export type Banner = OperationMessageData<"banner">;
export type AiInlineCompletionRequest = schemas["AiInlineCompletionRequest"];
export type DataTableColumn = schemas["DataTableColumn"];
export type DataTable = schemas["DataTable"];
export type Database = schemas["Database"];
export type DatabaseSchema = schemas["Schema"];
export type DataSourceConnection = schemas["DataSourceConnection"];
export type OutputChannel = schemas["CellChannel"];
export type MarimoError = schemas["Error"];
export type OutputMessage = schemas["CellOutput"];
export type CompletionOption = schemas["CompletionResult"]["options"][0];
export type CompletionResultMessage = OperationMessageData<"completion-result">;
export type HumanReadableStatus = schemas["HumanReadableStatus"];
export type FunctionCallResultMessage =
  OperationMessageData<"function-call-result">;
export type PackageInstallationStatus =
  schemas["InstallingPackageAlert"]["packages"];
export type DataColumnPreview = OperationMessageData<"data-column-preview">;
export type SQLTablePreview = OperationMessageData<"sql-table-preview">;
export type SQLTableListPreview =
  OperationMessageData<"sql-table-list-preview">;
export type SecretKeysResult = OperationMessageData<"secret-keys-result">;

export type OperationMessageType = schemas["MessageOperation"]["name"];
export type OperationMessage = {
  [Type in OperationMessageType]: {
    op: Type;
    data: Omit<Extract<schemas["MessageOperation"], { name: Type }>, "name">;
  };
}[OperationMessageType];

export type CellMessage = OperationMessageData<"cell-op">;

export type OperationMessageData<T extends OperationMessageType> = Omit<
  Extract<schemas["MessageOperation"], { name: T }>,
  "name"
>;

export type Capabilities = OperationMessageData<"kernel-ready">["capabilities"];
