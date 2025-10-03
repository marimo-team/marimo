/* Copyright 2024 Marimo. All rights reserved. */

import { type Mock, vi } from "vitest";
import type { EditRequests, RunRequests } from "@/core/network/types";

type RequestClient = {
  [K in keyof (EditRequests & RunRequests)]: Mock<
    (EditRequests & RunRequests)[K]
  >;
};

export const MockRequestClient = {
  create(overrides?: Partial<RequestClient>): RequestClient {
    return {
      // Edit requests
      sendComponentValues: vi.fn().mockResolvedValue({}),
      sendModelValue: vi.fn().mockResolvedValue({}),
      sendRename: vi.fn().mockResolvedValue({}),
      sendRestart: vi.fn().mockResolvedValue({}),
      syncCellIds: vi.fn().mockResolvedValue({}),
      sendSave: vi.fn().mockResolvedValue({}),
      sendCopy: vi.fn().mockResolvedValue({}),
      sendStdin: vi.fn().mockResolvedValue({}),
      sendFormat: vi.fn().mockResolvedValue({ codes: {} }),
      sendInterrupt: vi.fn().mockResolvedValue({}),
      sendShutdown: vi.fn().mockResolvedValue({}),
      sendRun: vi.fn().mockResolvedValue({}),
      sendRunScratchpad: vi.fn().mockResolvedValue({}),
      sendInstantiate: vi.fn().mockResolvedValue({}),
      sendDeleteCell: vi.fn().mockResolvedValue({}),
      sendCodeCompletionRequest: vi.fn().mockResolvedValue({ items: [] }),
      saveUserConfig: vi.fn().mockResolvedValue({}),
      saveAppConfig: vi.fn().mockResolvedValue({}),
      saveCellConfig: vi.fn().mockResolvedValue({}),
      sendFunctionRequest: vi.fn().mockResolvedValue({}),
      sendInstallMissingPackages: vi.fn().mockResolvedValue({}),
      readCode: vi.fn().mockResolvedValue({ contents: "" }),
      readSnippets: vi.fn().mockResolvedValue({ snippets: [] }),
      previewDatasetColumn: vi.fn().mockResolvedValue({}),
      previewSQLTable: vi.fn().mockResolvedValue({}),
      previewSQLTableList: vi.fn().mockResolvedValue({ tables: [] }),
      previewDataSourceConnection: vi.fn().mockResolvedValue({}),
      validateSQL: vi.fn().mockResolvedValue({}),
      openFile: vi.fn().mockResolvedValue({}),
      getUsageStats: vi.fn().mockResolvedValue({}),
      sendPdb: vi.fn().mockResolvedValue({}),
      sendListFiles: vi.fn().mockResolvedValue({ files: [] }),
      sendSearchFiles: vi
        .fn()
        .mockResolvedValue({ files: [], query: "", total_found: 0 }),
      sendCreateFileOrFolder: vi.fn().mockResolvedValue({}),
      sendDeleteFileOrFolder: vi.fn().mockResolvedValue({}),
      sendRenameFileOrFolder: vi.fn().mockResolvedValue({}),
      sendUpdateFile: vi.fn().mockResolvedValue({}),
      sendFileDetails: vi.fn().mockResolvedValue({}),
      openTutorial: vi.fn().mockResolvedValue({}),
      getRecentFiles: vi.fn().mockResolvedValue({ files: [] }),
      getWorkspaceFiles: vi.fn().mockResolvedValue({ files: [] }),
      getRunningNotebooks: vi.fn().mockResolvedValue({ files: [] }),
      shutdownSession: vi.fn().mockResolvedValue({}),
      exportAsHTML: vi.fn().mockResolvedValue({ html: "" }),
      exportAsMarkdown: vi.fn().mockResolvedValue({ markdown: "" }),
      autoExportAsHTML: vi.fn().mockResolvedValue({}),
      autoExportAsMarkdown: vi.fn().mockResolvedValue({}),
      autoExportAsIPYNB: vi.fn().mockResolvedValue({}),
      addPackage: vi.fn().mockResolvedValue({}),
      removePackage: vi.fn().mockResolvedValue({}),
      getPackageList: vi.fn().mockResolvedValue({ packages: [] }),
      getDependencyTree: vi.fn().mockResolvedValue({}),
      listSecretKeys: vi.fn().mockResolvedValue({ keys: [] }),
      writeSecret: vi.fn().mockResolvedValue({}),
      invokeAiTool: vi.fn().mockResolvedValue({}),
      ...overrides,
    };
  },
};
