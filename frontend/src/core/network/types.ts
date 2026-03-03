/* Copyright 2026 Marimo. All rights reserved. */
import type { components, paths } from "@marimo-team/marimo-api";
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
export type RuntimeState = schemas["CellNotification"]["status"];
export type CodeCompletionRequest = schemas["CodeCompletionRequest"];
export type DeleteCellRequest = schemas["DeleteCellRequest"];
export type ExportAsHTMLRequest = schemas["ExportAsHTMLRequest"];
export type ExportAsMarkdownRequest = schemas["ExportAsMarkdownRequest"];
export type ExportAsIPYNBRequest = schemas["ExportAsIPYNBRequest"];
export type ExportAsScriptRequest = schemas["ExportAsScriptRequest"];
export type ExportAsPDFRequest = schemas["ExportAsPDFRequest"];
export type UpdateCellOutputsRequest = schemas["UpdateCellOutputsRequest"];
export type FileCreateRequest = schemas["FileCreateRequest"];
export type FileCreateResponse = schemas["FileCreateResponse"];
export type FileDeleteRequest = schemas["FileDeleteRequest"];
export type FileDeleteResponse = schemas["FileDeleteResponse"];
export type FileDetailsRequest = schemas["FileDetailsRequest"];
export type FileDetailsResponse = schemas["FileDetailsResponse"];
export type FileInfo = schemas["FileInfo"];
export type FileListRequest = schemas["FileListRequest"];
export type FileListResponse = schemas["FileListResponse"];
export type FileSearchRequest = schemas["FileSearchRequest"];
export type FileSearchResponse = schemas["FileSearchResponse"];
export type FileMoveRequest = schemas["FileMoveRequest"];
export type FileMoveResponse = schemas["FileMoveResponse"];
export type FileUpdateRequest = schemas["FileUpdateRequest"];
export type FileUpdateResponse = schemas["FileUpdateResponse"];
export type FormatCellsRequest = schemas["FormatCellsRequest"];
export type FormatResponse = schemas["FormatResponse"];
export type InvokeFunctionRequest = schemas["InvokeFunctionRequest"];
export type ListSecretKeysResponse = schemas["ListSecretKeysResponse"];
export type InstallPackagesRequest = schemas["InstallPackagesRequest"];
export type AddPackageRequest = schemas["AddPackageRequest"];
export type RemovePackageRequest = schemas["RemovePackageRequest"];
export type ListPackagesResponse = schemas["ListPackagesResponse"];
export type DependencyTreeResponse = schemas["DependencyTreeResponse"];
export type DependencyTreeNode = schemas["DependencyTreeNode"];

export type PackageOperationResponse = schemas["PackageOperationResponse"];
export type InstantiateNotebookRequest = schemas["InstantiateNotebookRequest"];
export type MarimoConfig = schemas["MarimoConfig"];
export type MarimoFile = schemas["MarimoFile"];
export type ListSecretKeysRequest = schemas["ListSecretKeysRequest"];
export type CreateSecretRequest = schemas["CreateSecretRequest"];
export type PreviewDatasetColumnRequest =
  schemas["PreviewDatasetColumnRequest"];
export type PreviewSQLTableRequest = schemas["PreviewSQLTableRequest"];
export type ListSQLTablesRequest = schemas["ListSQLTablesRequest"];
export type ListDataSourceConnectionRequest =
  schemas["ListDataSourceConnectionRequest"];
export type ValidateSQLRequest = schemas["ValidateSQLRequest"];
export type DebugCellRequest = schemas["DebugCellRequest"];
export type ReadCodeResponse = schemas["ReadCodeResponse"];
export type RecentFilesResponse = schemas["RecentFilesResponse"];
export type RenameNotebookRequest = schemas["RenameNotebookRequest"];
export type ExecuteCellsRequest = schemas["ExecuteCellsRequest"];
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
export type UpdateUIElementRequest = schemas["UpdateUIElementRequest"];
export type ModelRequest = schemas["ModelRequest"];
export type UpdateCellIdsRequest = schemas["UpdateCellIdsRequest"];
export type UpdateUserConfigRequest = schemas["UpdateUserConfigRequest"];
export type ShutdownSessionRequest = schemas["ShutdownSessionRequest"];
export type Snippet = schemas["Snippet"];
export type SnippetSection = schemas["SnippetSection"];
export type Snippets = schemas["Snippets"];
export type StdinRequest = schemas["StdinRequest"];
export type SuccessResponse = schemas["SuccessResponse"];
export type UpdateUIElementValuesRequest =
  schemas["UpdateUIElementValuesRequest"];
export type UsageResponse =
  paths["/api/usage"]["get"]["responses"]["200"]["content"]["application/json"];
export type WorkspaceFilesRequest = schemas["WorkspaceFilesRequest"];
export type WorkspaceFilesResponse = schemas["WorkspaceFilesResponse"];
export type RunningNotebooksResponse = schemas["RunningNotebooksResponse"];
export type OpenTutorialRequest = schemas["OpenTutorialRequest"];
export type TutorialId = OpenTutorialRequest["tutorialId"];
export type InvokeAiToolRequest = schemas["InvokeAiToolRequest"];
export type InvokeAiToolResponse = schemas["InvokeAiToolResponse"];
export type ClearCacheRequest = schemas["ClearCacheRequest"];
export type GetCacheInfoRequest = schemas["GetCacheInfoRequest"];
export type LspHealthResponse = schemas["LspHealthResponse"];
export type LspRestartRequest = schemas["LspRestartRequest"];
export type LspRestartResponse = schemas["LspRestartResponse"];
export type LspServerHealth = schemas["LspServerHealth"];

export type StorageListEntriesRequest = schemas["StorageListEntriesRequest"];
export type StorageDownloadRequest = schemas["StorageDownloadRequest"];

/**
 * Requests sent to the BE during run/edit mode.
 */
export interface RunRequests {
  sendComponentValues: (request: UpdateUIElementValuesRequest) => Promise<null>;
  sendModelValue: (request: ModelRequest) => Promise<null>;
  sendInstantiate: (request: InstantiateNotebookRequest) => Promise<null>;
  sendFunctionRequest: (request: InvokeFunctionRequest) => Promise<null>;
}

/**
 * Requests sent to the BE during edit mode.
 */
export interface EditRequests {
  sendRename: (request: RenameNotebookRequest) => Promise<null>;
  sendSave: (request: SaveNotebookRequest) => Promise<null>;
  sendCopy: (request: CopyNotebookRequest) => Promise<null>;
  sendStdin: (request: StdinRequest) => Promise<null>;
  sendRun: (request: ExecuteCellsRequest) => Promise<null>;
  sendRunScratchpad: (request: ExecuteScratchpadRequest) => Promise<null>;
  sendInterrupt: () => Promise<null>;
  sendShutdown: () => Promise<null>;
  sendFormat: (request: FormatCellsRequest) => Promise<FormatResponse>;
  sendDeleteCell: (request: DeleteCellRequest) => Promise<null>;
  sendCodeCompletionRequest: (request: CodeCompletionRequest) => Promise<null>;
  saveUserConfig: (request: SaveUserConfigurationRequest) => Promise<null>;
  saveAppConfig: (request: SaveAppConfigurationRequest) => Promise<null>;
  saveCellConfig: (request: SetCellConfigRequest) => Promise<null>;
  sendRestart: () => Promise<null>;
  syncCellIds: (request: UpdateCellIdsRequest) => Promise<null>;
  sendInstallMissingPackages: (
    request: InstallPackagesRequest,
  ) => Promise<null>;
  readCode: () => Promise<{ contents: string }>;
  readSnippets: () => Promise<Snippets>;
  previewDatasetColumn: (request: PreviewDatasetColumnRequest) => Promise<null>;
  previewSQLTable: (request: PreviewSQLTableRequest) => Promise<null>;
  previewSQLTableList: (request: ListSQLTablesRequest) => Promise<null>;
  previewDataSourceConnection: (
    request: ListDataSourceConnectionRequest,
  ) => Promise<null>;
  validateSQL: (request: ValidateSQLRequest) => Promise<null>;
  openFile: (request: { path: string; lineNumber?: number }) => Promise<null>;
  getUsageStats: () => Promise<UsageResponse>;
  // Debugger
  sendPdb: (request: DebugCellRequest) => Promise<null>;
  // File explorer requests
  sendListFiles: (request: FileListRequest) => Promise<FileListResponse>;
  sendSearchFiles: (request: FileSearchRequest) => Promise<FileSearchResponse>;
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
  exportAsPDF: (request: ExportAsPDFRequest) => Promise<Blob>;
  autoExportAsHTML: (request: ExportAsHTMLRequest) => Promise<null>;
  autoExportAsMarkdown: (request: ExportAsMarkdownRequest) => Promise<null>;
  autoExportAsIPYNB: (request: ExportAsIPYNBRequest) => Promise<null>;
  updateCellOutputs: (request: UpdateCellOutputsRequest) => Promise<null>;
  // Package requests
  getPackageList: () => Promise<ListPackagesResponse>;
  getDependencyTree: () => Promise<DependencyTreeResponse>;
  addPackage: (request: AddPackageRequest) => Promise<PackageOperationResponse>;
  removePackage: (
    request: RemovePackageRequest,
  ) => Promise<PackageOperationResponse>;
  // Secrets requests
  listSecretKeys: (request: ListSecretKeysRequest) => Promise<null>;
  writeSecret: (request: CreateSecretRequest) => Promise<null>;
  // AI Tool requests
  invokeAiTool: (request: InvokeAiToolRequest) => Promise<InvokeAiToolResponse>;
  // Cache requests
  clearCache: () => Promise<null>;
  getCacheInfo: () => Promise<null>;
  // Storage requests
  listStorageEntries: (request: StorageListEntriesRequest) => Promise<null>;
  downloadStorage: (request: StorageDownloadRequest) => Promise<null>;
}

export type RequestKey = keyof (EditRequests & RunRequests);
