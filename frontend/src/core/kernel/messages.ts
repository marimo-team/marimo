/* Copyright 2024 Marimo. All rights reserved. */
import { type components } from "@marimo-team/marimo-api";

export type schemas = components["schemas"];
export type DataType = schemas["DataType"];
export type Banner = OperationMessageData<"banner">;
export type DataTableColumn = schemas["DataTableColumn"];
export type DataTable = schemas["DataTable"];
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
