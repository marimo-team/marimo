/* Copyright 2026 Marimo. All rights reserved. */
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
export type ModelLifecycle = NotificationMessageData<"model-lifecycle">;
export type Banner = NotificationMessageData<"banner">;
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
  { type: string }[]
>[number];
export type OutputMessage = schemas["CellOutput"];
export type CompletionOption =
  schemas["CompletionResultNotification"]["options"][0];
export type CompletionResultMessage =
  NotificationMessageData<"completion-result">;
export type HumanReadableStatus = schemas["HumanReadableStatus"];
export type FunctionCallResultMessage =
  NotificationMessageData<"function-call-result">;
export type PackageInstallationStatus =
  schemas["InstallingPackageAlertNotification"]["packages"];
export type DataColumnPreview = NotificationMessageData<"data-column-preview">;
export type SQLTablePreview = NotificationMessageData<"sql-table-preview">;
export type SQLTableListPreview =
  NotificationMessageData<"sql-table-list-preview">;
export type ValidateSQLResult = NotificationMessageData<"validate-sql-result">;
export type SecretKeysResult = NotificationMessageData<"secret-keys-result">;
export type StartupLogs = NotificationMessageData<"startup-logs">;
export type CellMessage = NotificationMessageData<"cell-op">;
export type Capabilities =
  NotificationMessageData<"kernel-ready">["capabilities"];
export type CacheInfoFetched = NotificationMessageData<"cache-info">;

export type NotificationMessage = schemas["KnownUnions"]["notification"];
export type CommandMessage = schemas["KnownUnions"]["command"];

export type NotificationMessageType = NotificationMessage["op"];
export interface NotificationPayload {
  data: NotificationMessage;
}

export type NotificationMessageData<T extends NotificationMessageType> = Omit<
  Extract<NotificationMessage, { op: T }>,
  "op"
>;
