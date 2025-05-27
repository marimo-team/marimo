/* Copyright 2024 Marimo. All rights reserved. */
import type { paths, components } from "@marimo-team/marimo-api";
import type { CellId } from "../cells/ids";

export type schemas = components["schemas"];
export type AiCompletionRequest = schemas["AiCompletionRequest"];
export type BaseResponse = schemas["BaseResponse"];
export type CellConfig = schemas["CellConfig"];
/**
 * The status of a cell.
 *
 * queued: queued by the kernel.
 * running: currently executing.
 * idle: not running.
 * disabled-transitively: disabled because an ancestor was disabled.
 */
export type RuntimeState = schemas["RuntimeState"];
export type CodeCompletionRequest = schemas["CodeCompletionRequest"];
export type DeleteCellRequest = schemas["DeleteCellRequest"];
export type ExecuteMultipleRequest = schemas["ExecuteMultipleRequest"];
export type ExecutionRequest = schemas["ExecutionRequest"];
export type ExportAsHTMLRequest = schemas["ExportAsHTMLRequest"];
export type ExportAsMarkdownRequest = schemas["ExportAsMarkdownRequest"];
export type ExportAsIPYNBRequest = schemas["ExportAsIPYNBRequest"];
export type ExportAsScriptRequest = schemas["ExportAsScriptRequest"];
export type FileCreateRequest = schemas["FileCreateRequest"];
export type FileCreateResponse = schemas["FileCreateResponse"];
export type FileDeleteRequest = schemas["FileDeleteRequest"];
export type FileDeleteResponse = schemas["FileDeleteResponse"];
export type FileDetailsRequest = schemas["FileDetailsRequest"];
export type FileDetailsResponse = schemas["FileDetailsResponse"];
export type FileInfo = schemas["FileInfo"];
export type FileListRequest = schemas["FileListRequest"];
export type FileListResponse = schemas["FileListResponse"];
export type FileMoveRequest = schemas["FileMoveRequest"];
export type FileMoveResponse = schemas["FileMoveResponse"];
export type FileUpdateRequest = schemas["FileUpdateRequest"];
export type FileUpdateResponse = schemas["FileUpdateResponse"];
export type FormatRequest = schemas["FormatRequest"];
export type FormatResponse = schemas["FormatResponse"];
export type FunctionCallRequest = schemas["FunctionCallRequest"];
export type ListSecretKeysResponse = schemas["ListSecretKeysResponse"];
export type InstallMissingPackagesRequest =
  schemas["InstallMissingPackagesRequest"];
export type AddPackageRequest = schemas["AddPackageRequest"];
export type RemovePackageRequest = schemas["RemovePackageRequest"];
export type ListPackagesResponse = schemas["ListPackagesResponse"];
export type PackageOperationResponse = schemas["PackageOperationResponse"];
export type InstantiateRequest = schemas["InstantiateRequest"];
export type MarimoConfig = schemas["MarimoConfig"];
export type MarimoFile = schemas["MarimoFile"];
export type ListSecretKeysRequest = schemas["ListSecretKeysRequest"];
export type CreateSecretRequest = schemas["CreateSecretRequest"];
export type PreviewDatasetColumnRequest =
  schemas["PreviewDatasetColumnRequest"];
export type PreviewSQLTableRequest = schemas["PreviewSQLTableRequest"];
export type PreviewSQLTableListRequest = schemas["PreviewSQLTableListRequest"];
export type PreviewDataSourceConnectionRequest =
  schemas["PreviewDataSourceConnectionRequest"];
export type PdbRequest = schemas["PdbRequest"];
export type ReadCodeResponse = schemas["ReadCodeResponse"];
export type RecentFilesResponse = schemas["RecentFilesResponse"];
export type RenameFileRequest = schemas["RenameFileRequest"];
export type RunRequest = schemas["RunRequest"];
export type ExecuteScratchpadRequest = schemas["ExecuteScratchpadRequest"];
export type SaveAppConfigurationRequest =
  schemas["SaveAppConfigurationRequest"];
export type SaveNotebookRequest = schemas["SaveNotebookRequest"];
export type CopyNotebookRequest = schemas["CopyNotebookRequest"];
export type SaveUserConfigurationRequest =
  schemas["SaveUserConfigurationRequest"];
export interface SetCellConfigRequest {
  configs: Record<CellId, Partial<CellConfig>>;
}
export type SetUIElementValueRequest = schemas["SetUIElementValueRequest"];
export type SetModelMessageRequest = schemas["SetModelMessageRequest"];
export type UpdateCellIdsRequest = schemas["UpdateCellIdsRequest"];
export type SetUserConfigRequest = schemas["SetUserConfigRequest"];
export type ShutdownSessionRequest = schemas["ShutdownSessionRequest"];
export type Snippet = schemas["Snippet"];
export type SnippetSection = schemas["SnippetSection"];
export type Snippets = schemas["Snippets"];
export type StdinRequest = schemas["StdinRequest"];
export type SuccessResponse = schemas["SuccessResponse"];
export type UpdateComponentValuesRequest =
  schemas["UpdateComponentValuesRequest"];
export type UsageResponse =
  paths["/api/usage"]["get"]["responses"]["200"]["content"]["application/json"];
export type WorkspaceFilesRequest = schemas["WorkspaceFilesRequest"];
export type WorkspaceFilesResponse = schemas["WorkspaceFilesResponse"];
export type RunningNotebooksResponse = schemas["RunningNotebooksResponse"];
export type OpenTutorialRequest = schemas["OpenTutorialRequest"];
export type TutorialId = OpenTutorialRequest["tutorialId"];

/**
 * Requests sent to the BE during run/edit mode.
 */
export interface RunRequests {
  sendComponentValues: (request: UpdateComponentValuesRequest) => Promise<null>;
  sendModelValue: (request: SetModelMessageRequest) => Promise<null>;
  sendInstantiate: (request: InstantiateRequest) => Promise<null>;
  sendFunctionRequest: (request: FunctionCallRequest) => Promise<null>;
}

/**
 * Requests sent to the BE during edit mode.
 */
export interface EditRequests {
  sendRename: (request: RenameFileRequest) => Promise<null>;
  sendSave: (request: SaveNotebookRequest) => Promise<null>;
  sendCopy: (request: CopyNotebookRequest) => Promise<null>;
  sendStdin: (request: StdinRequest) => Promise<null>;
  sendRun: (request: RunRequest) => Promise<null>;
  sendRunScratchpad: (request: ExecuteScratchpadRequest) => Promise<null>;
  sendInterrupt: () => Promise<null>;
  sendShutdown: () => Promise<null>;
  sendFormat: (request: FormatRequest) => Promise<FormatResponse>;
  sendDeleteCell: (request: DeleteCellRequest) => Promise<null>;
  sendCodeCompletionRequest: (request: CodeCompletionRequest) => Promise<null>;
  saveUserConfig: (request: SaveUserConfigurationRequest) => Promise<null>;
  saveAppConfig: (request: SaveAppConfigurationRequest) => Promise<null>;
  saveCellConfig: (request: SetCellConfigRequest) => Promise<null>;
  sendRestart: () => Promise<null>;
  syncCellIds: (request: UpdateCellIdsRequest) => Promise<null>;
  sendInstallMissingPackages: (
    request: InstallMissingPackagesRequest,
  ) => Promise<null>;
  readCode: () => Promise<{ contents: string }>;
  readSnippets: () => Promise<Snippets>;
  previewDatasetColumn: (request: PreviewDatasetColumnRequest) => Promise<null>;
  previewSQLTable: (request: PreviewSQLTableRequest) => Promise<null>;
  previewSQLTableList: (request: PreviewSQLTableListRequest) => Promise<null>;
  previewDataSourceConnection: (
    request: PreviewDataSourceConnectionRequest,
  ) => Promise<null>;
  openFile: (request: { path: string }) => Promise<null>;
  getUsageStats: () => Promise<UsageResponse>;
  // Debugger
  sendPdb: (request: PdbRequest) => Promise<null>;
  // File explorer requests
  sendListFiles: (request: FileListRequest) => Promise<FileListResponse>;
  sendCreateFileOrFolder: (
    request: FileCreateRequest,
  ) => Promise<FileCreateResponse>;
  sendDeleteFileOrFolder: (
    request: FileDeleteRequest,
  ) => Promise<FileDeleteResponse>;
  sendRenameFileOrFolder: (
    request: FileMoveRequest,
  ) => Promise<FileMoveResponse>;
  sendUpdateFile: (request: FileUpdateRequest) => Promise<FileUpdateResponse>;
  sendFileDetails: (request: { path: string }) => Promise<FileDetailsResponse>;
  // Homepage requests
  openTutorial: (request: OpenTutorialRequest) => Promise<MarimoFile>;
  getRecentFiles: () => Promise<RecentFilesResponse>;
  getWorkspaceFiles: (
    request: WorkspaceFilesRequest,
  ) => Promise<WorkspaceFilesResponse>;
  getRunningNotebooks: () => Promise<RunningNotebooksResponse>;
  shutdownSession: (
    request: ShutdownSessionRequest,
  ) => Promise<RunningNotebooksResponse>;
  // Export requests
  exportAsHTML: (request: ExportAsHTMLRequest) => Promise<string>;
  exportAsMarkdown: (request: ExportAsMarkdownRequest) => Promise<string>;
  autoExportAsHTML: (request: ExportAsHTMLRequest) => Promise<null>;
  autoExportAsMarkdown: (request: ExportAsMarkdownRequest) => Promise<null>;
  autoExportAsIPYNB: (request: ExportAsIPYNBRequest) => Promise<null>;
  // Package requests
  getPackageList: () => Promise<ListPackagesResponse>;
  addPackage: (request: AddPackageRequest) => Promise<PackageOperationResponse>;
  removePackage: (
    request: RemovePackageRequest,
  ) => Promise<PackageOperationResponse>;
  // Secrets requests
  listSecretKeys: (request: ListSecretKeysRequest) => Promise<null>;
  writeSecret: (request: CreateSecretRequest) => Promise<null>;
}

export type RequestKey = keyof (EditRequests & RunRequests);
