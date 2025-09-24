/* Copyright 2024 Marimo. All rights reserved. */
import type { components } from "@marimo-team/marimo-api";

export type schemas = components["schemas"];
export type DataType = schemas["KnownUnions"]["data_type"];
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
export type CellOutput = schemas["CellOutput"];
export type MarimoError = Extract<
  CellOutput["data"],
  Array<{ type: string }>
>[number];
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
export type ValidateSQLResult = OperationMessageData<"validate-sql-result">;
export type SecretKeysResult = OperationMessageData<"secret-keys-result">;
export type StartupLogs = OperationMessageData<"startup-logs">;
export type CellMessage = OperationMessageData<"cell-op">;
export type Capabilities = OperationMessageData<"kernel-ready">["capabilities"];

export type MessageOperationUnion = schemas["KnownUnions"]["operation"];

export type OperationMessageType = MessageOperationUnion["op"];
export interface OperationMessage {
  data: MessageOperationUnion;
}

export type OperationMessageData<T extends OperationMessageType> = Omit<
  Extract<MessageOperationUnion, { op: T }>,
  "op"
>;
