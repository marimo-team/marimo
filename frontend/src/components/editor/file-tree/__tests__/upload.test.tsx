/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import type { FileCreateInput, FileCreateResponse } from "@/core/network/types";
import type { FilePath } from "@/utils/paths";
import {
  FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE,
  getUploadDestinationFromTarget,
  resolveUploadDirectoryPath,
  uploadFilesToDestination,
} from "../upload";

const filePath = (path: string) => path as FilePath;

describe("resolveUploadDirectoryPath", () => {
  it("uploads an individual file to the explicit destination", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("/workspace/data"),
        filePath: filePath("./sales.csv"),
      }),
    ).toBe("/workspace/data");
  });

  it("preserves a dropped folder's relative structure", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("/workspace/data"),
        filePath: filePath("raw/2026/sales.csv"),
      }),
    ).toBe("/workspace/data/raw/2026");
  });

  it("normalizes relative paths for a Windows destination", () => {
    expect(
      resolveUploadDirectoryPath({
        destinationPath: filePath("C:\\workspace\\data"),
        filePath: filePath("raw/2026/sales.csv"),
      }),
    ).toBe("C:\\workspace\\data\\raw\\2026");
  });
});

describe("getUploadDestinationFromTarget", () => {
  it("uses the closest folder as the drop destination", () => {
    const folder = document.createElement("div");
    folder.setAttribute(
      FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE,
      "/workspace/data",
    );
    const child = document.createElement("span");
    folder.append(child);

    expect(getUploadDestinationFromTarget(child, filePath("/workspace"))).toBe(
      "/workspace/data",
    );
  });

  it("uses the workspace root outside a folder", () => {
    expect(
      getUploadDestinationFromTarget(
        document.createElement("div"),
        filePath("/workspace"),
      ),
    ).toBe("/workspace");
  });
});

describe("uploadFilesToDestination", () => {
  it("sends files to the destination and separates server failures", async () => {
    const successfulFile = new File(["success"], "success.txt");
    const failedFile = new File(["failure"], "failure.txt");
    Object.defineProperty(successfulFile, "path", {
      value: "nested/success.txt",
    });
    const createFile = vi.fn(
      async (request: FileCreateInput): Promise<FileCreateResponse> =>
        request.name === "success.txt"
          ? { success: true }
          : { success: false, message: "Permission denied" },
    );
    const onFileProcessed = vi.fn();

    const result = await uploadFilesToDestination({
      files: [successfulFile, failedFile],
      destinationPath: filePath("/workspace/data"),
      createFile,
      onFileProcessed,
    });

    expect(createFile.mock.calls.map(([request]) => request)).toEqual([
      {
        path: "/workspace/data/nested",
        type: "file",
        name: "success.txt",
        file: successfulFile,
      },
      {
        path: "/workspace/data",
        type: "file",
        name: "failure.txt",
        file: failedFile,
      },
    ]);
    expect(result).toEqual({
      successful: [{ file: successfulFile, response: { success: true } }],
      failed: [
        {
          file: failedFile,
          response: { success: false, message: "Permission denied" },
        },
      ],
    });
    expect(onFileProcessed).toHaveBeenCalledTimes(2);
  });
});
